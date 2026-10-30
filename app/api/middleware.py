import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.logging import request_id_ctx

_SKIP_RATE_LIMIT = {
    "/health",
    "/api/v1/health",
    "/api/v1/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)


rate_limit_hits: dict[str, deque[float]] = defaultdict(deque)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-IP limiter. Disabled when rate_limit_per_minute is 0."""

    async def dispatch(self, request: Request, call_next) -> Response:
        limit = settings.rate_limit_per_minute
        if limit <= 0 or request.url.path in _SKIP_RATE_LIMIT:
            return await call_next(request)

        now = time.monotonic()
        key = request.client.host if request.client else "unknown"
        window = rate_limit_hits[key]
        cutoff = now - 60.0
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": f"Rate limit of {limit} requests per minute exceeded.",
                },
            )
        window.append(now)
        return await call_next(request)
