"""Redis-backed monthly budget guard."""
from datetime import datetime, timezone

from fastapi import HTTPException
from redis import Redis

INPUT_PRICE_PER_1K = 0.00015
OUTPUT_PRICE_PER_1K = 0.0006


def estimate_tokens(text: str) -> int:
    # Lightweight approximation for this lab.
    return max(1, len(text.split()) * 2)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    input_cost = (input_tokens / 1000) * INPUT_PRICE_PER_1K
    output_cost = (output_tokens / 1000) * OUTPUT_PRICE_PER_1K
    return input_cost + output_cost


def check_and_record_monthly_budget(
    redis_client: Redis,
    user_id: str,
    input_tokens: int,
    output_tokens: int,
    monthly_budget_usd: float,
) -> float:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    key = f"budget:{user_id}:{month}"
    cost = estimate_cost_usd(input_tokens, output_tokens)

    current = float(redis_client.get(key) or 0.0)
    projected = current + cost

    if projected > monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(current, 6),
                "requested_usd": round(cost, 6),
                "budget_usd": monthly_budget_usd,
                "month": month,
            },
        )

    pipeline = redis_client.pipeline(transaction=True)
    pipeline.incrbyfloat(key, cost)
    pipeline.expire(key, 33 * 24 * 3600)
    pipeline.execute()

    return projected
