"""API middleware (CORS, security headers, rate limiting)."""

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses."""

    async def dispatch(self, request: Request, call_next):
        logger.info(
            "request_received",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else "unknown",
        )

        response = await call_next(request)

        logger.info(
            "response_sent",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._request_counts: dict = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        # Simple in-memory rate limiting (use Redis in production)
        import time

        current_time = int(time.time() / 60)

        key = f"{client_ip}:{current_time}"
        count = self._request_counts.get(key, 0)

        if count >= self.requests_per_minute:
            logger.warning("rate_limit_exceeded", client=client_ip)
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "ERR_RATE_LIMIT",
                        "message": "Too many requests. Please try again later.",
                    }
                },
            )

        self._request_counts[key] = count + 1
        return await call_next(request)


def setup_middleware(app):
    """Setup all middleware for the application."""
    from fastapi import FastAPI

    # Add CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add custom middleware
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    # app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    logger.info("middleware_configured")
