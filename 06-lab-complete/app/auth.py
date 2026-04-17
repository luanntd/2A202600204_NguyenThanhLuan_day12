"""Authentication helpers: API key (required path) + JWT (bonus path)."""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

from app.config import settings


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Validate API key from X-API-Key header."""
    if not x_api_key or x_api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return x_api_key


def create_jwt_token(username: str, role: str = "admin") -> str:
    payload = {
        "sub": username,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_jwt_token(authorization: str | None) -> dict | None:
    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must use Bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return {
            "username": payload.get("sub", "unknown"),
            "role": payload.get("role", "user"),
        }
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=403, detail="Invalid token") from exc
