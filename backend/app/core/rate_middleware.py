"""Rate limiting middleware."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.rate_limit import api_limiter, write_limiter, login_limiter, get_client_ip
from loguru import logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limiting to all API requests."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Skip non-API paths
        if not path.startswith("/api/"):
            return await call_next(request)

        # Health check exempt
        if path in ("/health", "/"):
            return await call_next(request)

        ip = get_client_ip(request)

        # Select limiter based on path/method
        if "/auth/login" in path:
            limiter = login_limiter
        elif method in ("POST", "PUT", "DELETE"):
            limiter = write_limiter
        else:
            limiter = api_limiter

        if not limiter.is_allowed(ip):
            logger.warning(f"Rate limit exceeded: {ip} {method} {path}")
            return JSONResponse(
                status_code=429,
                content={"code": 429, "message": f"请求过于频繁，请{limiter.window_seconds}秒后重试", "data": None},
            )

        response = await call_next(request)
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limiter.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(limiter.get_remaining(ip))
        return response
