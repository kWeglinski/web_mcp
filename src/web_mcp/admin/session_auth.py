"""Session-based authentication for the admin panel.

Uses signed cookies (no external dependencies) for session management.
The session secret key is derived from WEB_MCP_ADMIN_API_KEY.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SESSION_COOKIE_NAME = "admin_session"
SESSION_MAX_AGE = 86400  # 24 hours in seconds
ADMIN_API_KEY = os.environ.get("WEB_MCP_ADMIN_API_KEY", "")
ADMIN_PATH_PREFIX = os.environ.get("WEB_MCP_ADMIN_PATH", "/admin")

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/admin/login",
    "/admin/logout",
    "/admin/health",
}


def create_session_token(password: str) -> str:
    """Create a signed session token.

    Args:
        password: The admin API key used as the signing secret.

    Returns:
        A signed token string in the format "timestamp.signature".
    """
    timestamp = str(int(time.time()))
    message = f"{timestamp}:{password}"
    signature = hmac.new(password.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}.{signature}"


def verify_session_token(token: str, password: str) -> bool:
    """Verify a session token is valid and not expired.

    Args:
        token: The session token to verify.
        password: The admin API key used for verification.

    Returns:
        True if the token is valid and not expired.
    """
    try:
        timestamp_str, signature = token.split(".")
        timestamp = int(timestamp_str)
        expected_message = f"{timestamp_str}:{password}"
        expected_signature = hmac.new(
            password.encode(), expected_message.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return False
        # Check expiry (24 hours)
        if time.time() - timestamp > SESSION_MAX_AGE:
            return False
        return True
    except (ValueError, AttributeError):
        return False


def _set_session_cookie(response: Response, token: str, request: Request) -> None:
    """Set the session cookie on a response.

    Args:
        response: The Starlette response to set the cookie on.
        token: The session token to set.
        request: The incoming request (for determining secure flag).
    """
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=is_secure,
        samesite="lax",
    )


def _clear_session_cookie(response: Response, request: Request) -> None:
    """Clear the session cookie by setting it to empty with past expiry.

    Args:
        response: The Starlette response to clear the cookie on.
        request: The incoming request (for determining secure flag).
    """
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        expires=0,
    )


def _is_public_path(path: str) -> bool:
    """Check if a path is public (no auth required).

    Args:
        path: The URL path to check.

    Returns:
        True if the path doesn't require authentication.
    """
    # Exact match for public paths
    if path in PUBLIC_PATHS:
        return True
    # Also match with trailing slash
    if path.rstrip("/") in PUBLIC_PATHS:
        return True
    return False


class AdminSessionMiddleware(BaseHTTPMiddleware):
    """Middleware that protects /admin/* endpoints with session-based auth."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for non-admin paths
        if not path.startswith(ADMIN_PATH_PREFIX):
            return await call_next(request)

        # Skip auth for public admin paths
        if _is_public_path(path):
            return await call_next(request)

        # Check for API key header as fallback (backward compat)
        api_key = request.headers.get("X-Admin-Key")
        if api_key and api_key == ADMIN_API_KEY:
            return await call_next(request)

        # Check session cookie
        session_token = request.cookies.get(SESSION_COOKIE_NAME)
        if session_token and verify_session_token(session_token, ADMIN_API_KEY):
            return await call_next(request)

        return JSONResponse(
            {"error": "Unauthorized"},
            status_code=401,
        )


class LoginHandler:
    """Handles login/logout requests for the admin panel."""

    @staticmethod
    async def handle_login(request: Request) -> Response:
        """Handle POST /admin/login — authenticate and set session cookie.

        Expects JSON body: { "password": "..." }
        """
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"error": "Invalid request body"},
                status_code=400,
            )

        password = body.get("password", "")

        if not password or password != ADMIN_API_KEY:
            return JSONResponse(
                {"error": "Invalid password"},
                status_code=401,
            )

        token = create_session_token(ADMIN_API_KEY)
        response = JSONResponse({"status": "ok"})
        _set_session_cookie(response, token, request)
        return response

    @staticmethod
    async def handle_logout(request: Request) -> Response:
        """Handle POST /admin/logout — clear session cookie.

        Always succeeds (idempotent).
        """
        response = JSONResponse({"status": "ok"})
        _clear_session_cookie(response, request)
        return response
