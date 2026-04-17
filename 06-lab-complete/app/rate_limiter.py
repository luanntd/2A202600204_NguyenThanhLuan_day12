"""Redis-based sliding window rate limiter."""
import time

from fastapi import HTTPException
from redis import Redis


def enforce_rate_limit(redis_client: Redis, user_id: str, max_requests: int, window_seconds: int = 60) -> None:
    now = time.time()
    key = f"rate:{user_id}"
    pipeline = redis_client.pipeline(transaction=True)

    # Keep only entries in the current window.
    pipeline.zremrangebyscore(key, 0, now - window_seconds)
    pipeline.zcard(key)
    _, current_count = pipeline.execute()

    if int(current_count) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {max_requests} req/min",
            headers={"Retry-After": str(window_seconds)},
        )

    pipeline = redis_client.pipeline(transaction=True)
    pipeline.zadd(key, {f"{now}": now})
    pipeline.expire(key, window_seconds + 5)
    pipeline.execute()
