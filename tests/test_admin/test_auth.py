"""Unit tests for AdminSessionMiddleware (replaces old API key auth tests)."""

import importlib
import os

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.routing import Route
from starlette.testclient import TestClient


def _make_json_response(request: Request):
    from starlette.responses import JSONResponse

    return JSONResponse({"message": "ok"})


def _build_app(api_key="test-secret-key"):
    """Build a Starlette app with session auth middleware for testing."""
    os.environ["WEB_MCP_ADMIN_API_KEY"] = api_key

    import web_mcp.admin.session_auth as session_auth_module

    importlib.reload(session_auth_module)

    from web_mcp.admin.ui import AdminUI

    app = Starlette(
        routes=[
            Route("/health", _make_json_response, methods=["GET"]),
            Route("/admin/health", _make_json_response, methods=["GET"]),
            Route("/admin/login", AdminUI.serve_login, methods=["GET"]),
            Route("/admin/login", session_auth_module.LoginHandler.handle_login, methods=["POST"]),
            Route(
                "/admin/logout", session_auth_module.LoginHandler.handle_logout, methods=["POST"]
            ),
            Route("/admin/data", _make_json_response, methods=["GET"]),
            Route("/admin/config/paths", _make_json_response, methods=["GET"]),
            Route("/other", _make_json_response, methods=["GET"]),
        ],
        middleware=[Middleware(session_auth_module.AdminSessionMiddleware)],
    )
    return app, session_auth_module


class TestValidSessionLogin:
    """Tests for valid session login flow."""

    def test_valid_login_then_access(self):
        """Test login sets cookie and subsequent requests succeed."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.post("/admin/login", json={"password": "test-secret-key"})
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            resp = client.get("/admin/data")
            assert resp.status_code == 200
            assert resp.json() == {"message": "ok"}


class TestInvalidPassword:
    """Tests for invalid password."""

    def test_invalid_password(self):
        """Test wrong password → 401."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.post("/admin/login", json={"password": "wrong-key"})
            assert resp.status_code == 401
            assert resp.json()["error"] == "Invalid password"

    def test_missing_password(self):
        """Test empty password → 401."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.post("/admin/login", json={"password": ""})
            assert resp.status_code == 401


class TestMissingAuth:
    """Tests for missing authentication."""

    def test_no_auth_header_or_cookie(self):
        """Test no auth → 401."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.get("/admin/data")
            assert resp.status_code == 401
            assert resp.json()["error"] == "Unauthorized"


class TestNonAdminPath:
    """Tests for non-admin path bypassing auth."""

    def test_non_admin_path(self):
        """Test /health bypasses auth."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"message": "ok"}

    def test_other_path_no_auth(self):
        """Test /other bypasses auth."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.get("/other")
            assert resp.status_code == 200


class TestBackwardCompatApiKeyHeader:
    """Tests for backward-compatible X-Admin-Key header fallback."""

    def test_valid_key_header(self):
        """Test correct X-Admin-Key header → 200 (passes through)."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.get("/admin/data", headers={"X-Admin-Key": "test-secret-key"})
            assert resp.status_code == 200
            assert resp.json() == {"message": "ok"}

    def test_invalid_key_header(self):
        """Test wrong X-Admin-Key header → 401."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.get("/admin/data", headers={"X-Admin-Key": "wrong-key"})
            assert resp.status_code == 401
            assert resp.json()["error"] == "Unauthorized"


class TestLogout:
    """Tests for logout functionality."""

    def test_logout_clears_session(self):
        """Test logout clears the session cookie."""
        app, _ = _build_app()

        with TestClient(app) as client:
            client.post("/admin/login", json={"password": "test-secret-key"})
            resp = client.get("/admin/data")
            assert resp.status_code == 200

            resp = client.post("/admin/logout")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            resp = client.get("/admin/data")
            assert resp.status_code == 401

    def test_logout_without_login(self):
        """Test logout works even without a prior login."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.post("/admin/logout")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}


class TestPublicPaths:
    """Tests that public paths are accessible without auth."""

    def test_login_page_accessible(self):
        """Test GET /admin/login returns the login page."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.get("/admin/login")
            assert resp.status_code == 200
            assert b"Web MCP Admin" in resp.content

    def test_health_no_auth_required(self):
        """Test /admin/health is accessible without auth."""
        app, _ = _build_app()

        with TestClient(app) as client:
            resp = client.get("/admin/health")
            assert resp.status_code == 200
            assert resp.json() == {"message": "ok"}
