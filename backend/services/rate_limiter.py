"""
backend/services/rate_limiter.py
──────────────────────────────────
In-memory token-bucket rate limiter for FastAPI.
Integrates with slowapi for per-IP limiting.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ── SlowAPI Limiter (decorator-based) ─────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Token-Bucket Rate Limiter (manual, thread-safe) ───────────────────────────

class TokenBucket:
    """A simple token-bucket rate limiter for a single client."""

    def __init__(self, capacity: int, refill_rate: float) -> None:
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_rate  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Attempt to consume `tokens` tokens. Returns True if allowed."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.refill_rate,
            )
            self._last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


class RateLimiterService:
    """
    Per-client rate limiter backed by in-memory token buckets.

    Authenticated users get more tokens than anonymous ones.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(
                capacity=settings.rate_limit_requests,
                refill_rate=settings.rate_limit_requests / settings.rate_limit_period,
            )
        )
        self._auth_buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(
                capacity=settings.rate_limit_requests * 3,
                refill_rate=(settings.rate_limit_requests * 3) / settings.rate_limit_period,
            )
        )

    def check(self, client_id: str, authenticated: bool = False) -> None:
        """
        Check rate limit. Raises HTTP 429 if the limit is exceeded.

        Parameters
        ----------
        client_id     : IP address or user ID.
        authenticated : Whether the client is authenticated.
        """
        bucket = (
            self._auth_buckets[client_id]
            if authenticated
            else self._buckets[client_id]
        )
        if not bucket.consume():
            logger.warning("Rate limit exceeded", client_id=client_id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Rate limit exceeded. "
                    f"Anonymous users: {settings.rate_limit_requests} requests "
                    f"per {settings.rate_limit_period}s. "
                    "Sign in for a higher limit."
                ),
                headers={"Retry-After": str(settings.rate_limit_period)},
            )


# ── Module-level singleton ────────────────────────────────────────────────────
_rate_limiter_service: RateLimiterService | None = None


def get_rate_limiter() -> RateLimiterService:
    global _rate_limiter_service
    if _rate_limiter_service is None:
        _rate_limiter_service = RateLimiterService()
    return _rate_limiter_service
