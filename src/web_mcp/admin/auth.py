"""API key authentication middleware for admin endpoints."""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

ADMIN_API_KEY = os.environ.get("WEB_MCP_ADMIN_API_KEY", "")
ADMIN_PATH_PREFIX = os.environ.get("WEB_MCP_ADMIN_PATH", "/admin")


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that protects /admin/* endpoints with an API key."""

    async def dispatch(self, request: Request, call_next):
        # If the request path is not under the admin prefix, skip auth
        if not request.url.path.startswith(ADMIN_PATH_PREFIX):
            return await call_next(request)
        if request.url.path.startswith(ADMIN_PATH_PREFIX):
            if not ADMIN_API_KEY:
                return JSONResponse(
                    {"error": "Admin API key not configured"},
                    status_code=503,
                )
            api_key = (
                request.headers.get("X-Admin-Key")
                or request.query_params.get("api_key")
            )
            if not api_key or api_key != ADMIN_API_KEY:
                return JSONResponse(
                    {"error": "Unauthorized"},
                    status_code=401,
                )
        response = await call_next(request)
        return response
