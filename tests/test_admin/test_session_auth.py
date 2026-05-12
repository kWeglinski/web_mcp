"""Unit tests for session-based admin authentication."""

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


def _build_session_app(api_key="test-secret-key"):
    """Build a Starlette app with session auth middleware for testing."""
    os.environ["WEB_MCP_ADMIN_API_KEY"] = api_key

    # Reload the session_auth module to pick up new env vars
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
            Route("/admin/dashboard", _make_json_response, methods=["GET"]),
            Route("/admin/config/paths", _make_json_response, methods=["GET"]),
            Route("/other", _make_json_response, methods=["GET"]),
        ],
        middleware=[Middleware(session_auth_module.AdminSessionMiddleware)],
    )
    return app, session_auth_module


class TestSessionTokenCreation:
    """Tests for session token creation and verification."""

    def test_create_token_format(self):
        """Test that a token is created in timestamp.signature format."""
        import web_mcp.admin.session_auth as sa

        importlib.reload(sa)
        token = sa.create_session_token("secret")
        parts = token.split(".")
        assert len(parts) == 2
        assert parts[0].isdigit()  # timestamp
        assert len(parts[1]) == 64  # SHA-256 hex digest

    def test_different_passwords_produce_different_tokens(self):
        """Test that different passwords produce different tokens."""
        import web_mcp.admin.session_auth as sa

        importlib.reload(sa)
        token1 = sa.create_session_token("secret1")
        token2 = sa.create_session_token("secret2")
        assert token1 != token2

    def test_verify_valid_token(self):
        """Test that a valid token verifies successfully."""
        import web_mcp.admin.session_auth as sa

        importlib.reload(sa)
        token = sa.create_session_token("mysecret")
        assert sa.verify_session_token(token, "mysecret") is True

    def test_verify_invalid_password(self):
        """Test that a token created with one password fails with another."""
        import web_mcp.admin.session_auth as sa

        importlib.reload(sa)
        token = sa.create_session_token("secret1")
        assert sa.verify_session_token(token, "secret2") is False

    def test_verify_corrupted_token(self):
        """Test that a corrupted token fails verification."""
        import web_mcp.admin.session_auth as sa

        importlib.reload(sa)
        token = sa.create_session_token("secret")
        corrupted = token[:-5] + "xxxxx"
        assert sa.verify_session_token(corrupted, "secret") is False

    def test_verify_malformed_token(self):
        """Test that malformed tokens fail verification."""
        import web_mcp.admin.session_auth as sa

        importlib.reload(sa)
        assert sa.verify_session_token("not-a-token", "secret") is False
        assert sa.verify_session_token("", "secret") is False
        assert sa.verify_session_token("onlytimestamp", "secret") is False


class TestSessionMiddleware:
    """Tests for AdminSessionMiddleware."""

    def test_valid_login_then_access(self):
        """Test login sets cookie and subsequent requests succeed."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            # Login
            resp = client.post(
                "/admin/login",
                json={"password": "test-secret-key"},
            )
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            # Dashboard should now be accessible
            resp = client.get("/admin/dashboard")
            assert resp.status_code == 200
            assert resp.json() == {"message": "ok"}

    def test_login_wrong_password(self):
        """Test login with wrong password returns 401."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            resp = client.post(
                "/admin/login",
                json={"password": "wrong-password"},
            )
            assert resp.status_code == 401
            assert resp.json()["error"] == "Invalid password"

            # Dashboard should still be inaccessible
            resp = client.get("/admin/dashboard")
            assert resp.status_code == 401

    def test_login_missing_password(self):
        """Test login with empty password returns 401."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            resp = client.post("/admin/login", json={"password": ""})
            assert resp.status_code == 401

    def test_login_invalid_json(self):
        """Test login with invalid JSON body returns 400."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            resp = client.post(
                "/admin/login", content="not json", headers={"Content-Type": "application/json"}
            )
            assert resp.status_code == 400

    def test_login_page_accessible(self):
        """Test GET /admin/login returns the login page."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            resp = client.get("/admin/login")
            assert resp.status_code == 200
            assert b"Web MCP Admin" in resp.content

    def test_logout_clears_session(self):
        """Test logout clears the session cookie."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            # Login first
            client.post("/admin/login", json={"password": "test-secret-key"})

            # Access dashboard
            resp = client.get("/admin/dashboard")
            assert resp.status_code == 200

            # Logout
            resp = client.post("/admin/logout")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

            # Dashboard should now be inaccessible
            resp = client.get("/admin/dashboard")
            assert resp.status_code == 401

    def test_logout_without_login(self):
        """Test logout works even without a prior login (idempotent)."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            resp = client.post("/admin/logout")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}

    def test_health_no_auth_required(self):
        """Test /admin/health is accessible without auth."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            resp = client.get("/admin/health")
            assert resp.status_code == 200
            assert resp.json() == {"message": "ok"}

    def test_non_admin_path_no_auth(self):
        """Test non-admin paths bypass session auth."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            resp = client.get("/other")
            assert resp.status_code == 200

    def test_unauthenticated_admin_access(self):
        """Test unauthenticated access to admin routes returns 401."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            resp = client.get("/admin/dashboard")
            assert resp.status_code == 401
            assert resp.json()["error"] == "Unauthorized"

            resp = client.get("/admin/config/paths")
            assert resp.status_code == 401

    def test_backward_compat_api_key_header(self):
        """Test X-Admin-Key header still works as fallback."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            # No login, but using the API key header should work
            resp = client.get("/admin/dashboard", headers={"X-Admin-Key": "test-secret-key"})
            assert resp.status_code == 200
            assert resp.json() == {"message": "ok"}

    def test_api_key_header_wrong_value(self):
        """Test wrong X-Admin-Key header returns 401."""
        app, sa = _build_session_app()

        with TestClient(app) as client:
            resp = client.get("/admin/dashboard", headers={"X-Admin-Key": "wrong-key"})
            assert resp.status_code == 401


class TestPublicPaths:
    """Tests that public paths are correctly identified."""

    def test_public_paths(self):
        """Test that public paths don't require auth."""
        import web_mcp.admin.session_auth as sa

        importlib.reload(sa)
        assert sa._is_public_path("/admin/login") is True
        assert sa._is_public_path("/admin/logout") is True
        assert sa._is_public_path("/admin/health") is True
        assert sa._is_public_path("/admin/login/") is True
        assert sa._is_public_path("/admin/logout/") is True
        assert sa._is_public_path("/admin/health/") is True

    def test_non_public_paths(self):
        """Test that non-public paths require auth."""
        import web_mcp.admin.session_auth as sa

        importlib.reload(sa)
        assert sa._is_public_path("/admin/dashboard") is False
        assert sa._is_public_path("/admin/config") is False
        assert sa._is_public_path("/admin/config/paths") is False
        assert sa._is_public_path("/admin/tools") is False
