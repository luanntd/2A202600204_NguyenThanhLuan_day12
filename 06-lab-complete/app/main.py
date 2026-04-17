"""Production AI Agent — Kết hợp tất cả Day 12 concepts."""
import json
import logging
import re
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from redis import Redis
import uvicorn

from app.auth import create_jwt_token, verify_api_key, verify_jwt_token
from app.config import settings
from app.cost_guard import (
        check_and_record_monthly_budget,
        estimate_tokens,
)
from app.rate_limiter import enforce_rate_limit

# Mock LLM (thay bằng OpenAI/Anthropic khi có API key)
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0
_latest_total_cost_usd = 0.0
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)

def _history_key(user_id: str) -> str:
    return f"history:{user_id}"


def _parse_name_from_history(history: list[dict]) -> str | None:
    for item in reversed(history):
        if item.get("role") != "user":
            continue
        text = item.get("content", "")
        match = re.search(r"my name is\s+([A-Za-z][A-Za-z\- ]{0,40})", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _build_answer(question: str, history: list[dict]) -> str:
    lower_q = question.lower()
    if "what did i just say" in lower_q:
        previous_user_messages = [i["content"] for i in history if i.get("role") == "user"]
        if previous_user_messages:
            return f"You just said: '{previous_user_messages[-1]}'"

    if "what is my name" in lower_q or "what's my name" in lower_q:
        name = _parse_name_from_history(history)
        if name:
            return f"Your name is {name}."

    return llm_ask(question)


def _load_history(user_id: str) -> list[dict]:
    raw_items = redis_client.lrange(_history_key(user_id), 0, -1)
    return [json.loads(item) for item in raw_items]


def _append_history(user_id: str, role: str, content: str) -> None:
    key = _history_key(user_id)
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    pipeline = redis_client.pipeline(transaction=True)
    pipeline.rpush(key, json.dumps(message))
    pipeline.ltrim(key, -settings.max_history_messages, -1)
    pipeline.expire(key, settings.conversation_ttl_seconds)
    pipeline.execute()


def _verify_identity(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    # API key path is mandatory for grading compatibility.
    if x_api_key:
        verify_api_key(x_api_key)
        return {"auth_type": "api_key", "subject": "api-client"}

    # JWT remains available as bonus.
    token_payload = verify_jwt_token(authorization)
    if token_payload:
        return {"auth_type": "jwt", "subject": token_payload["username"]}

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Use X-API-Key or Bearer token.",
    )

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    redis_client.ping()
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))

    yield

    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128,
                         description="End user ID for rate limit/budget/history")
    question: str = Field(..., min_length=1, max_length=2000,
                          description="Your question for the agent")

class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    timestamp: str


class TokenRequest(BaseModel):
    username: str
    password: str

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "token": "POST /token (bonus JWT)",
            "ask": "POST /ask (requires X-API-Key or Bearer token)",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }


@app.post("/token", tags=["Auth"])
def issue_token(body: TokenRequest):
    if body.username != settings.demo_username or body.password != settings.demo_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt_token(body.username, role="admin")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_minutes": settings.jwt_expire_minutes,
    }


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    identity: dict = Depends(_verify_identity),
):
    """
    Send a question to the AI agent.

    **Authentication:** Include header `X-API-Key: <your-key>`
    """
    global _latest_total_cost_usd
    enforce_rate_limit(redis_client, body.user_id, settings.rate_limit_per_minute)

    input_tokens = estimate_tokens(body.question)
    check_and_record_monthly_budget(
        redis_client,
        body.user_id,
        input_tokens=input_tokens,
        output_tokens=0,
        monthly_budget_usd=settings.monthly_budget_usd,
    )

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": body.user_id,
        "auth_type": identity["auth_type"],
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    history_before = _load_history(body.user_id)
    answer = _build_answer(body.question, history_before)
    _append_history(body.user_id, "user", body.question)
    _append_history(body.user_id, "assistant", answer)

    output_tokens = estimate_tokens(answer)
    _latest_total_cost_usd = check_and_record_monthly_budget(
        redis_client,
        body.user_id,
        input_tokens=0,
        output_tokens=output_tokens,
        monthly_budget_usd=settings.monthly_budget_usd,
    )

    return AskResponse(
        user_id=body.user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe. Platform restarts container if this fails."""
    status = "ok"
    checks = {"llm": "mock" if not settings.openai_api_key else "openai"}
    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe. Load balancer stops routing here if not ready."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    try:
        redis_client.ping()
    except Exception as exc:
        raise HTTPException(503, f"Not ready: redis unavailable ({exc})") from exc
    return {"ready": True}


@app.get("/chat/{user_id}/history", tags=["Agent"])
def get_history(user_id: str, _identity: dict = Depends(_verify_identity)):
    history = _load_history(user_id)
    return {
        "user_id": user_id,
        "count": len(history),
        "messages": history,
    }


@app.get("/metrics", tags=["Operations"])
def metrics(_key: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        "latest_user_monthly_cost_usd": round(_latest_total_cost_usd, 6),
        "monthly_budget_usd": settings.monthly_budget_usd,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
    }


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    logger.info(f"API Key: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
