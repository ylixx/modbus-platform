"""Simple in-memory rate limiter for API endpoints.

Uses a sliding window counter per IP.
"""
import time
from collections import defaultdict
from fastapi import Request, HTTPException
from loguru import logger


class RateLimiter:
    """In-memory rate limiter with configurable window and max requests."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._sweep_counter = 0

    def is_allowed(self, key: str) -> bool:
        """Check if a request is allowed for the given key."""
        now = time.time()
        window_start = now - self.window_seconds

        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if t > window_start]

        if len(self._requests[key]) >= self.max_requests:
            return False

        self._requests[key].append(now)

        # Periodic global sweep so the dict can't grow unbounded
        # (one entry per distinct key would otherwise leak forever).
        self._sweep_counter += 1
        if self._sweep_counter % 1000 == 0:
            self._sweep()
        return True

    def _sweep(self) -> None:
        """Drop expired entries and evict keys with no recent activity."""
        now = time.time()
        cutoff = now - self.window_seconds * 2
        for k in list(self._requests.keys()):
            lst = self._requests[k]
            lst[:] = [t for t in lst if t > cutoff]
            if not lst:
                del self._requests[k]

    def get_remaining(self, key: str) -> int:
        """Get remaining requests for the key."""
        now = time.time()
        window_start = now - self.window_seconds
        recent = [t for t in self._requests[key] if t > window_start]
        return max(0, self.max_requests - len(recent))


# Global rate limiters
api_limiter = RateLimiter(max_requests=200, window_seconds=60)   # General API
write_limiter = RateLimiter(max_requests=30, window_seconds=60)  # Write operations
login_limiter = RateLimiter(max_requests=10, window_seconds=60)  # Login attempts


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request, limiter: RateLimiter = None):
    """Check rate limit for the current request."""
    limiter = limiter or api_limiter
    ip = get_client_ip(request)
    if not limiter.is_allowed(ip):
        raise HTTPException(
            status_code=429,
            detail=f"请求过于频繁，请{limiter.window_seconds}秒后重试",
        )
