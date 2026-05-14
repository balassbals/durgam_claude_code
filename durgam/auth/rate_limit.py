"""Redis-backed rate limiter for login and password-reset endpoints."""

from __future__ import annotations

import redis

from durgam.config import settings


class RateLimitExceeded(Exception):
    """Raised when a rate limit threshold is breached."""

    def __init__(self, key: str, limit: int) -> None:
        super().__init__(f"Rate limit exceeded for {key!r} (limit={limit})")
        self.key = key
        self.limit = limit


def _client() -> redis.Redis:  # type: ignore[type-arg]
    return redis.from_url(settings.redis_url, decode_responses=True)


def check_and_record(key: str, limit: int, window_seconds: int) -> int:
    """Increment the counter for *key* and raise RateLimitExceeded if over limit.

    Uses a sliding fixed-window counter implemented with Redis INCR + EXPIRE.
    Returns the current count after incrementing.
    """
    r = _client()
    count = r.incr(key)
    if count == 1:
        r.expire(key, window_seconds)
    if count > limit:
        raise RateLimitExceeded(key, limit)
    return count


def current_count(key: str) -> int:
    """Return the current counter value for *key* (0 if absent)."""
    r = _client()
    val = r.get(key)
    return int(val) if val is not None else 0


def reset(key: str) -> None:
    """Delete the counter for *key* (used in tests and after successful login)."""
    _client().delete(key)
