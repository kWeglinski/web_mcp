"""Unit tests for AdminAuthMiddleware."""

import importlib

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.routing import Route
from starlette.testclient import TestClient


def _make_health_response(request: Request):
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok"})


def _make_admin_response(request: Request):
    from starlette.responses import JSONResponse

    return JSONResponse({"admin": "data"})


def _build_app(middleware_class, admin_path_prefix="/admin", api_key="test-secret-key"):
    """Build a Starlette app with the given middleware for testing."""
    import os

    os.environ["WEB_MCP_ADMIN_API_KEY"] = api_key
    os.environ["WEB_MCP_ADMIN_PATH"] = admin_path_prefix

    # Reload the auth module to pick up new env vars
    import web_mcp.admin.auth as auth_module

    importlib.reload(auth_module)

    app = Starlette(
        routes=[
            Route("/health", _make_health_response, methods=["GET"]),
            Route("/admin/data", _make_admin_response, methods=["GET"]),
            Route("/admin/config/paths", _make_admin_response, methods=["GET"]),
            Route("/other", _make_health_response, methods=["GET"]),
        ],
        middleware=[Middleware(middleware_class)],
    )
    return app


class TestValidKeyHeader:
    """Tests for valid API key via header."""

    def test_valid_key_header(self):
        """Test correct X-Admin-Key header → 200 (passes through)."""
        import web_mcp.admin.auth as auth_module

        app = _build_app(auth_module.AdminAuthMiddleware)

        with TestClient(app) as client:
            response = client.get("/admin/data", headers={"X-Admin-Key": "test-secret-key"})

        assert response.status_code == 200
        assert response.json() == {"admin": "data"}


class TestValidKeyQueryParam:
    """Tests for valid API key via query parameter."""

    def test_valid_key_query_param(self):
        """Test correct api_key query param → 200."""
        import web_mcp.admin.auth as auth_module

        app = _build_app(auth_module.AdminAuthMiddleware)

        with TestClient(app) as client:
            response = client.get("/admin/data", params={"api_key": "test-secret-key"})

        assert response.status_code == 200
        assert response.json() == {"admin": "data"}


class TestInvalidKey:
    """Tests for invalid API key."""

    def test_invalid_key(self):
        """Test wrong key → 401."""
        import web_mcp.admin.auth as auth_module

        app = _build_app(auth_module.AdminAuthMiddleware)

        with TestClient(app) as client:
            response = client.get("/admin/data", headers={"X-Admin-Key": "wrong-key"})

        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"

    def test_invalid_key_query_param(self):
        """Test wrong api_key query param → 401."""
        import web_mcp.admin.auth as auth_module

        app = _build_app(auth_module.AdminAuthMiddleware)

        with TestClient(app) as client:
            response = client.get("/admin/data", params={"api_key": "wrong-key"})

        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"


class TestMissingKey:
    """Tests for missing API key."""

    def test_missing_key(self):
        """Test no key → 401."""
        import web_mcp.admin.auth as auth_module

        app = _build_app(auth_module.AdminAuthMiddleware)

        with TestClient(app) as client:
            response = client.get("/admin/data")

        assert response.status_code == 401
        assert response.json()["error"] == "Unauthorized"


class TestNonAdminPath:
    """Tests for non-admin path bypassing auth."""

    def test_non_admin_path(self):
        """Test /health bypasses auth."""
        import web_mcp.admin.auth as auth_module

        app = _build_app(auth_module.AdminAuthMiddleware)

        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_other_path_no_auth(self):
        """Test /other bypasses auth."""
        import web_mcp.admin.auth as auth_module

        app = _build_app(auth_module.AdminAuthMiddleware)

        with TestClient(app) as client:
            response = client.get("/other")

        assert response.status_code == 200


class TestNoApiKeyConfigured:
    """Tests for when no API key is configured."""

    def test_no_api_key_configured(self):
        """Test empty ADMIN_API_KEY → 503."""
        import web_mcp.admin.auth as auth_module

        app = _build_app(auth_module.AdminAuthMiddleware, api_key="")

        with TestClient(app) as client:
            response = client.get("/admin/data")

        assert response.status_code == 503
        assert response.json()["error"] == "Admin API key not configured"

    def test_no_api_key_on_non_admin_path(self):
        """Test non-admin path still works when no API key is configured."""
        import web_mcp.admin.auth as auth_module

        app = _build_app(auth_module.AdminAuthMiddleware, api_key="")

        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200
