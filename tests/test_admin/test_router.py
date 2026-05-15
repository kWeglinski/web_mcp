"""Unit tests for AdminRouter REST endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request

from web_mcp.admin.router import AdminRouter


def _make_mock_routing():
    """Create a mock PathRouter for testing."""
    routing = MagicMock()
    return routing


def _make_mock_storage():
    """Create a mock ConfigStorage for testing."""
    storage = MagicMock()
    storage.get_paths.return_value = {}
    storage.get_path_config.return_value = None
    storage.set_path_config.return_value = None
    storage.delete_path_config.return_value = False
    storage.get_all_tool_names.return_value = [
        "get_page",
        "render_html",
        "search_web",
        "brave_search",
        "search_metrics",
        "health",
        "current_datetime",
        "create_chart_tool",
        "run_javascript",
    ]
    return storage


@pytest.fixture
def mock_storage():
    """Fixture providing a mock ConfigStorage."""
    return _make_mock_storage()


@pytest.fixture
def mock_routing():
    """Fixture providing a mock PathRouter."""
    return _make_mock_routing()


@pytest.fixture
def admin_router(mock_routing, mock_storage):
    """Fixture providing an AdminRouter with mocked dependencies."""
    with patch(
        "web_mcp.admin.router.AdminRouter._check_auth", new_callable=AsyncMock
    ) as mock_check:
        mock_check.side_effect = lambda req, handler: handler()
        with patch("web_mcp.admin.router.ConfigStorage", return_value=mock_storage):
            router = AdminRouter(mock_routing)
            router._storage = mock_storage
            yield router


def _make_request(method, path, json_body=None, path_params=None):
    """Create a mock Starlette Request for testing."""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "server": ("localhost", 8000),
    }
    if path_params:
        scope["path_params"] = path_params

    request = Request(scope=scope)

    async def mock_json():
        return json_body

    request.json = mock_json
    return request


class TestListTools:
    """Tests for list_tools endpoint."""

    async def test_list_tools(self, admin_router):
        """Test returns all 14 tools with correct metadata."""
        response = await admin_router.list_tools(_make_request("GET", "/admin/tools"))

        data = response.body
        import json

        parsed = json.loads(data)
        tools = parsed["tools"]

        assert len(tools) == 14
        tool_names = [t["name"] for t in tools]
        assert "get_page" in tool_names
        assert "search_web" in tool_names
        assert "run_javascript" in tool_names
        assert "add_memory" in tool_names
        assert "search_memory" in tool_names
        assert "get_user_memories" in tool_names

        # Check metadata
        run_js = next(t for t in tools if t["name"] == "run_javascript")
        assert run_js["is_read_only"] is False
        assert run_js["destructive"] is True

        get_page = next(t for t in tools if t["name"] == "get_page")
        assert get_page["is_read_only"] is True
        assert get_page["destructive"] is False

        add_mem = next(t for t in tools if t["name"] == "add_memory")
        assert add_mem["is_read_only"] is True

        search_mem = next(t for t in tools if t["name"] == "search_memory")
        assert search_mem["is_read_only"] is True


class TestHealth:
    """Tests for health endpoint."""

    async def test_health(self, admin_router):
        """Test returns healthy status."""
        response = await admin_router.health(_make_request("GET", "/admin/health"))

        data = response.body
        import json

        parsed = json.loads(data)
        assert parsed["status"] == "healthy"
        assert parsed["version"] == "1.0.0"
        assert parsed["admin_enabled"] is True


class TestListPathsEmpty:
    """Tests for list_paths endpoint with no paths."""

    async def test_list_paths_empty(self, admin_router, mock_storage):
        """Test no paths configured → empty."""
        mock_storage.get_paths.return_value = {}

        response = await admin_router.list_paths(_make_request("GET", "/admin/config/paths"))

        data = response.body
        import json

        parsed = json.loads(data)
        assert parsed == {}


class TestCreatePath:
    """Tests for create_path endpoint."""

    async def test_create_path(self, admin_router, mock_storage):
        """Test creates new path config, returns 201."""
        mock_storage.get_all_tool_names.return_value = ["get_page", "health"]
        mock_storage.get_paths.return_value = {}

        body = {
            "path": "/search",
            "name": "Search",
            "description": "Search endpoint",
            "enabled_tools": ["get_page", "health"],
            "requires_auth": True,
        }
        request = _make_request("POST", "/admin/config/paths", json_body=body)

        response = await admin_router.create_path(request)

        assert response.status_code == 201
        data = response.body
        import json

        parsed = json.loads(data)
        assert parsed["status"] == "created"
        assert parsed["path"] == "/search"
        mock_storage.set_path_config.assert_called_once()

    async def test_create_path_invalid(self, admin_router):
        """Test rejects invalid paths."""
        body = {
            "path": "/bad path",
            "name": "Bad Path",
            "enabled_tools": ["get_page"],
        }
        request = _make_request("POST", "/admin/config/paths", json_body=body)

        response = await admin_router.create_path(request)

        assert response.status_code == 400
        data = response.body
        import json

        parsed = json.loads(data)
        assert "error" in parsed
        assert "Invalid path" in parsed["error"]

    async def test_create_path_unknown_tool(self, admin_router, mock_storage):
        """Test rejects unknown tool names."""
        mock_storage.get_all_tool_names.return_value = ["get_page", "health"]

        body = {
            "path": "/search",
            "name": "Search",
            "enabled_tools": ["get_page", "nonexistent_tool"],
        }
        request = _make_request("POST", "/admin/config/paths", json_body=body)

        response = await admin_router.create_path(request)

        assert response.status_code == 400
        data = response.body
        import json

        parsed = json.loads(data)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    async def test_create_path_missing_path_field(self, admin_router):
        """Test rejects request without path field."""
        body = {"name": "No Path", "enabled_tools": ["get_page"]}
        request = _make_request("POST", "/admin/config/paths", json_body=body)

        response = await admin_router.create_path(request)

        assert response.status_code == 400
        data = response.body
        import json

        parsed = json.loads(data)
        assert parsed["error"] == "path is required"


class TestGetPathNotFound:
    """Tests for get_path endpoint when path not found."""

    async def test_get_path_not_found(self, admin_router, mock_storage):
        """Test returns 404."""
        mock_storage.get_path_config.return_value = None

        request = _make_request(
            "GET", "/admin/config/paths/nonexistent", path_params={"path": "nonexistent"}
        )

        response = await admin_router.get_path(request)

        assert response.status_code == 404
        data = response.body
        import json

        parsed = json.loads(data)
        assert "error" in parsed
        assert "Path not found" in parsed["error"]


class TestGetPathFound:
    """Tests for get_path endpoint when path exists."""

    async def test_get_path_found(self, admin_router, mock_storage):
        """Test returns config."""
        mock_storage.get_path_config.return_value = {
            "name": "Search",
            "description": "Search endpoint",
            "enabled_tools": ["get_page", "health"],
            "requires_auth": True,
        }

        request = _make_request("GET", "/admin/config/paths/search", path_params={"path": "search"})

        response = await admin_router.get_path(request)

        assert response.status_code == 200
        data = response.body
        import json

        parsed = json.loads(data)
        assert parsed["name"] == "Search"
        assert parsed["enabled_tools"] == ["get_page", "health"]


class TestUpdatePath:
    """Tests for update_path endpoint."""

    async def test_update_path(self, admin_router, mock_storage):
        """Test updates existing config."""
        existing_config = {
            "name": "Old Name",
            "description": "Old desc",
            "enabled_tools": ["get_page"],
            "requires_auth": True,
        }
        mock_storage.get_path_config.return_value = existing_config
        mock_storage.get_all_tool_names.return_value = ["get_page", "health"]

        body = {"name": "New Name", "description": "New desc"}
        request = _make_request(
            "PUT", "/admin/config/paths/search", json_body=body, path_params={"path": "search"}
        )

        response = await admin_router.update_path(request)

        assert response.status_code == 200
        data = response.body
        import json

        parsed = json.loads(data)
        assert parsed["status"] == "updated"
        assert parsed["path"] == "search"
        mock_storage.set_path_config.assert_called_once()


class TestDeletePath:
    """Tests for delete_path endpoint."""

    async def test_delete_path(self, admin_router, mock_storage):
        """Test removes path, returns 200."""
        mock_storage.delete_path_config.return_value = True

        request = _make_request(
            "DELETE", "/admin/config/paths/search", path_params={"path": "search"}
        )

        response = await admin_router.delete_path(request)

        assert response.status_code == 200
        data = response.body
        import json

        parsed = json.loads(data)
        assert parsed["status"] == "deleted"
        assert parsed["path"] == "search"

    async def test_delete_path_not_found(self, admin_router, mock_storage):
        """Test returns 404 for nonexistent path."""
        mock_storage.delete_path_config.return_value = False

        request = _make_request(
            "DELETE", "/admin/config/paths/nonexistent", path_params={"path": "nonexistent"}
        )

        response = await admin_router.delete_path(request)

        assert response.status_code == 404
        data = response.body
        import json

        parsed = json.loads(data)
        assert "error" in parsed
        assert "Path not found" in parsed["error"]


class TestGetConfig:
    """Tests for get_config endpoint."""

    async def test_get_config(self, admin_router, mock_storage):
        """Test returns full config."""
        mock_storage.get_paths.return_value = {
            "/search": {
                "name": "Search",
                "enabled_tools": ["get_page"],
            }
        }

        response = await admin_router.get_config(_make_request("GET", "/admin/config"))

        assert response.status_code == 200
        data = response.body
        import json

        parsed = json.loads(data)
        assert "paths" in parsed
        assert "/search" in parsed["paths"]


class TestUpdateConfig:
    """Tests for update_config endpoint."""

    async def test_update_config(self, admin_router, mock_storage):
        """Test replaces all paths."""
        mock_storage.get_paths.return_value = {}
        mock_storage.get_all_tool_names.return_value = ["get_page", "health"]

        body = {
            "paths": {
                "/search": {"name": "Search", "enabled_tools": ["get_page"]},
                "/research": {"name": "Research", "enabled_tools": ["health"]},
            }
        }
        request = _make_request("POST", "/admin/config", json_body=body)

        response = await admin_router.update_config(request)

        assert response.status_code == 200
        data = response.body
        import json

        parsed = json.loads(data)
        assert parsed["status"] == "ok"
        assert parsed["paths"] == 2
