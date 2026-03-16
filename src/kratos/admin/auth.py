from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import select

from ..models import ApiKey


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that validates the x-api-key header on every request."""

    def __init__(self, app, session_factory):
        super().__init__(app)
        self._session_factory = session_factory

    async def dispatch(self, request: Request, call_next):
        # Allow OpenAPI docs through without auth
        if request.url.path in ("/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        api_key = request.headers.get("x-api-key")
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing x-api-key header"},
            )

        stmt = select(ApiKey).where(ApiKey.key == api_key, ApiKey.is_active.is_(True))
        with self._session_factory.session() as session:
            row = session.execute(stmt).scalar_one_or_none()

        if row is None:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid or revoked API key"},
            )

        return await call_next(request)
