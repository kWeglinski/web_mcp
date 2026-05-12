"""Unit tests for path_routing module."""

from unittest.mock import MagicMock

from starlette.routing import Route

from web_mcp.path_routing import (
    PathConfig,
    PathRouter,
    get_all_tool_names,
    get_tool_descriptions,
    validate_path,
)


class TestPathConfigCreation:
    """Tests for PathConfig class creation."""

    def test_path_config_creation(self):
        """Test default values."""
        mock_mcp = MagicMock()
        config = PathConfig(path="/search", mcp=mock_mcp, name="Search")

        assert config.path == "/search"
        assert config.mcp is mock_mcp
        assert config.name == "Search"
        assert config.description == ""
        assert config.enabled_tools == []
        assert config.requires_auth is True

    def test_path_config_strips_trailing_slash(self):
        """Test trailing slash is stripped."""
        mock_mcp = MagicMock()
        config = PathConfig(path="/search/", mcp=mock_mcp, name="Search")

        assert config.path == "/search"

    def test_path_config_root_path(self):
        """Test root path stays as /."""
        mock_mcp = MagicMock()
        config = PathConfig(path="/", mcp=mock_mcp, name="Root")

        assert config.path == "/"

    def test_path_config_with_all_params(self):
        """Test with all parameters specified."""
        mock_mcp = MagicMock()
        config = PathConfig(
            path="/research",
            mcp=mock_mcp,
            name="Research",
            description="Research endpoint",
            enabled_tools=["get_page", "search_web"],
            requires_auth=False,
        )

        assert config.path == "/research"
        assert config.description == "Research endpoint"
        assert config.enabled_tools == ["get_page", "search_web"]
        assert config.requires_auth is False


class TestPathRouterAddAndList:
    """Tests for PathRouter add and list operations."""

    def test_path_router_add_and_list(self):
        """Test adding paths and listing them."""
        router = PathRouter()
        mock_mcp1 = MagicMock()
        mock_mcp2 = MagicMock()

        config1 = PathConfig(path="/search", mcp=mock_mcp1, name="Search")
        config2 = PathConfig(path="/research", mcp=mock_mcp2, name="Research")

        router.add_path(config1)
        router.add_path(config2)

        paths = router.paths
        assert len(paths) == 2
        assert "/search" in paths
        assert "/research" in paths

    def test_path_router_empty(self):
        """Test empty router has no paths."""
        router = PathRouter()
        assert router.paths == []


class TestPathRouterRemove:
    """Tests for PathRouter remove operation."""

    def test_path_router_remove(self):
        """Test removing a path."""
        router = PathRouter()
        mock_mcp = MagicMock()

        config = PathConfig(path="/search", mcp=mock_mcp, name="Search")
        router.add_path(config)

        result = router.remove_path("/search")
        assert result is True
        assert "/search" not in router.paths

    def test_path_router_remove_nonexistent(self):
        """Test removing a nonexistent path."""
        router = PathRouter()

        result = router.remove_path("/nonexistent")
        assert result is False
        assert router.paths == []


class TestPathRouterGetNonexistent:
    """Tests for PathRouter get operations on nonexistent paths."""

    def test_path_router_get_nonexistent(self):
        """Test get_path_config returns None for nonexistent path."""
        router = PathRouter()

        result = router.get_path_config("/nonexistent")
        assert result is None


class TestPathRouterSetDefault:
    """Tests for PathRouter set_default operation."""

    def test_path_router_set_default(self):
        """Test setting a default MCP instance."""
        router = PathRouter()
        mock_mcp = MagicMock()

        router.set_default(mock_mcp)

        # The default MCP is stored internally, verify via _default_mcp
        assert router._default_mcp is mock_mcp


class TestValidatePathValid:
    """Tests for validate_path with valid paths."""

    def test_validate_path_valid(self):
        """Test valid paths: /search, /research, /my-path."""
        assert validate_path("/search") is True
        assert validate_path("/research") is True
        assert validate_path("/my-path") is True

    def test_validate_path_with_underscore(self):
        """Test path with underscore is valid."""
        assert validate_path("/my_path") is True

    def test_validate_path_with_numbers(self):
        """Test path with numbers is valid."""
        assert validate_path("/api/v1") is True

    def test_validate_path_nested(self):
        """Test nested path is valid."""
        assert validate_path("/api/v1/search") is True


class TestValidatePathInvalid:
    """Tests for validate_path with invalid paths."""

    def test_validate_path_invalid(self):
        """Test invalid paths: /, /bad path, /has/space, etc."""
        assert validate_path("/") is False
        assert validate_path("/bad path") is False
        assert validate_path("/has space") is False
        assert validate_path("search") is False  # missing leading slash
        assert validate_path("/has.dot") is False  # dot not allowed
        assert validate_path("/has?query") is False  # query param not allowed
        assert validate_path("") is False  # empty string

    def test_validate_path_with_special_chars(self):
        """Test paths with special characters are invalid."""
        assert validate_path("/has!@#") is False
        assert validate_path("/has &") is False
        assert validate_path("/has<>") is False


class TestBuildStarletteApp:
    """Tests for PathRouter.build_starlette_app."""

    def test_build_starlette_app(self):
        """Test verify routes are registered."""
        router = PathRouter()
        mock_mcp = MagicMock()
        mock_mcp.sse_app.return_value = MagicMock()

        config = PathConfig(path="/search", mcp=mock_mcp, name="Search")
        router.add_path(config)

        admin_routes = [Route("/admin", lambda r: None, methods=["GET"])]
        app = router.build_starlette_app(admin_routes=admin_routes)

        assert isinstance(app, type(router.build_starlette_app()))

        # Check that routes contain Mount for MCP and Route for admin/health
        route_paths = [r.path for r in app.routes]
        assert "/health" in route_paths
        assert "/admin" in route_paths
        # The MCP mount path should be in routes
        assert "/search" in route_paths

    def test_build_starlette_app_no_admin(self):
        """Test building app with no admin routes."""
        router = PathRouter()
        mock_mcp = MagicMock()
        mock_mcp.sse_app.return_value = MagicMock()

        config = PathConfig(path="/search", mcp=mock_mcp, name="Search")
        router.add_path(config)

        app = router.build_starlette_app()

        route_paths = [r.path for r in app.routes]
        assert "/health" in route_paths
        assert "/search" in route_paths
        # No admin routes should be present
        assert "/admin" not in route_paths

    def test_build_starlette_app_with_default(self):
        """Test building app with default MCP."""
        router = PathRouter()
        mock_mcp = MagicMock()
        mock_mcp.sse_app.return_value = MagicMock()

        router.set_default(mock_mcp)

        app = router.build_starlette_app()

        route_paths = [r.path for r in app.routes]
        assert "/default" in route_paths
        assert "/health" in route_paths


class TestGetAllToolNames:
    """Tests for get_all_tool_names function."""

    def test_get_all_tool_names(self):
        """Test returns 9 tool names."""
        tool_names = get_all_tool_names()

        assert len(tool_names) == 9
        assert "get_page" in tool_names
        assert "search_web" in tool_names
        assert "run_javascript" in tool_names


class TestGetToolDescriptions:
    """Tests for get_tool_descriptions function."""

    def test_get_tool_descriptions(self):
        """Test returns dict of 9 tool names to descriptions."""
        descriptions = get_tool_descriptions()

        assert len(descriptions) == 9
        assert "get_page" in descriptions
        assert "search_web" in descriptions
        assert isinstance(descriptions["get_page"], str)
        assert len(descriptions["get_page"]) > 0

    def test_descriptions_are_nonempty(self):
        """Test all descriptions are non-empty strings."""
        descriptions = get_tool_descriptions()

        for _name, desc in descriptions.items():
            assert isinstance(desc, str)
            assert len(desc) > 0
