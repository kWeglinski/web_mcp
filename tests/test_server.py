"""Unit tests for server module (create_app, auth, tool registration)."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestStaticTokenVerifier:
    @pytest.mark.asyncio
    async def test_verify_token_correct(self):
        from web_mcp.server import StaticTokenVerifier

        verifier = StaticTokenVerifier("my-secret-token")
        result = await verifier.verify_token("my-secret-token")
        assert result is not None
        assert result.token == "my-secret-token"
        assert result.client_id == "static"

    @pytest.mark.asyncio
    async def test_verify_token_incorrect(self):
        from web_mcp.server import StaticTokenVerifier

        verifier = StaticTokenVerifier("my-secret-token")
        result = await verifier.verify_token("wrong-token")
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_token_empty(self):
        from web_mcp.server import StaticTokenVerifier

        verifier = StaticTokenVerifier("my-secret-token")
        result = await verifier.verify_token("")
        assert result is None

    def test_expected_token_stored(self):
        from web_mcp.server import StaticTokenVerifier

        verifier = StaticTokenVerifier("token123")
        assert verifier.expected_token == "token123"


class TestCreateAuthConfig:
    def test_create_auth_config_with_token(self):
        import os

        with patch.dict(os.environ, {"WEB_MCP_AUTH_TOKEN": "test-token-123"}):
            with (
                patch("web_mcp.server.SERVER_HOST", "0.0.0.0"),
                patch("web_mcp.server.SERVER_PORT", 8000),
            ):
                from web_mcp.server import StaticTokenVerifier, create_auth_config

                verifier, settings = create_auth_config()
                assert verifier is not None
                assert isinstance(verifier, StaticTokenVerifier)
                assert settings is not None
                assert "test-token-123" in verifier.expected_token

    def test_create_auth_config_without_token(self):
        import os

        if "WEB_MCP_AUTH_TOKEN" in os.environ:
            del os.environ["WEB_MCP_AUTH_TOKEN"]

        with (
            patch("web_mcp.server.SERVER_HOST", "0.0.0.0"),
            patch("web_mcp.server.SERVER_PORT", 8000),
        ):
            from web_mcp.server import create_auth_config

            verifier, settings = create_auth_config()
            assert verifier is None
            assert settings is None


class TestServerConstants:
    def test_server_host_default(self):
        import os

        if "WEB_MCP_SERVER_HOST" in os.environ:
            del os.environ["WEB_MCP_SERVER_HOST"]
        if "WEB_MCP_SERVER_PORT" in os.environ:
            del os.environ["WEB_MCP_SERVER_PORT"]

        host = os.environ.get("WEB_MCP_SERVER_HOST", "0.0.0.0")
        port = int(os.environ.get("WEB_MCP_SERVER_PORT", "8000"))
        assert host == "0.0.0.0"
        assert port == 8000

    def test_output_schemas_default(self):
        import os

        if "WEB_MCP_OUTPUT_SCHEMAS" in os.environ:
            del os.environ["WEB_MCP_OUTPUT_SCHEMAS"]
        result = os.environ.get("WEB_MCP_OUTPUT_SCHEMAS", "").lower() in ("true", "1", "yes")
        assert result is False


class TestToolRegistry:
    def test_tool_registry_has_expected_tools(self):
        from web_mcp.server import TOOL_REGISTRY

        expected_tools = [
            "get_page",
            "render_html",
            "search_web",
            "brave_search",
            "search_metrics",
            "wikipedia_search",
            "wikipedia_research",
            "health",
            "current_datetime",
            "create_chart_tool",
            "run_javascript",
            "add_memory",
            "search_memory",
            "get_user_memories",
            "gather_knowledge",
            "search_knowledge",
            "manage_knowledge_collection",
        ]

        for tool in expected_tools:
            assert tool in TOOL_REGISTRY, f"Missing tool: {tool}"

    def test_tool_registry_get_page(self):
        from web_mcp.server import TOOL_REGISTRY

        tool = TOOL_REGISTRY["get_page"]
        assert tool["name"] == "get_page"
        assert tool["is_read_only"] is True
        assert tool["module"] == "tools.fetching"

    def test_tool_registry_health(self):
        from web_mcp.server import TOOL_REGISTRY

        tool = TOOL_REGISTRY["health"]
        assert tool["name"] == "health"
        assert tool["is_read_only"] is True
        assert tool["module"] == "tools.utils"

    def test_tool_registry_brave_search(self):
        from web_mcp.server import TOOL_REGISTRY

        tool = TOOL_REGISTRY["brave_search"]
        assert tool["name"] == "brave_search"
        assert tool["module"] == "tools.search"


class TestRegisterTools:
    def test_register_tool_helper(self):
        from web_mcp.server import _register_tool

        mock_mcp = MagicMock()
        mock_fn = MagicMock()

        _register_tool(mock_mcp, mock_fn)

        mock_mcp.add_tool.assert_called_once_with(
            mock_fn, annotations=None, structured_output=False
        )

    def test_register_tool_with_annotations(self):
        from mcp.types import ToolAnnotations

        from web_mcp.server import _register_tool

        mock_mcp = MagicMock()
        mock_fn = MagicMock()
        annotations = ToolAnnotations(readOnlyHint=True)

        _register_tool(mock_mcp, mock_fn, annotations, True)

        mock_mcp.add_tool.assert_called_once_with(
            mock_fn, annotations=annotations, structured_output=True
        )

    def test_register_all_tools(self):
        mock_mem0_tools = MagicMock()
        mock_mem0_tools.add_memory_tool = MagicMock()
        mock_mem0_tools.search_memory_tool = MagicMock()
        mock_mem0_tools.get_user_memories_tool = MagicMock()

        mock_fetching = MagicMock()
        mock_fetching.get_page = MagicMock()
        mock_fetching.render_html = MagicMock()

        mock_search = MagicMock()
        mock_search.search_web = MagicMock()
        mock_search.brave_search = MagicMock()
        mock_search.wikipedia_search = MagicMock()
        mock_search.wikipedia_research = MagicMock()
        mock_search.search_metrics = MagicMock()

        mock_utils = MagicMock()
        mock_utils.health = MagicMock()
        mock_utils.current_datetime = MagicMock()

        mock_advanced = MagicMock()
        mock_advanced.create_chart_tool = MagicMock()
        mock_advanced.run_javascript = MagicMock()

        with (
            patch("web_mcp.server.FastMCP"),
            patch.dict(
                sys.modules,
                {
                    "web_mcp.mem0.tools": mock_mem0_tools,
                    "web_mcp.tools.fetching": mock_fetching,
                    "web_mcp.tools.search": mock_search,
                    "web_mcp.tools.utils": mock_utils,
                    "web_mcp.tools.advanced": mock_advanced,
                },
            ),
            patch("web_mcp.server.gather_knowledge"),
            patch("web_mcp.server.search_knowledge"),
            patch("web_mcp.server.manage_knowledge_collection"),
            patch("web_mcp.server.ToolAnnotations"),
        ):
            from web_mcp.server import register_all_tools

            mock_mcp = MagicMock()
            register_all_tools(mock_mcp)

            mock_mcp.add_tool.assert_called()
            call_count = mock_mcp.add_tool.call_count
            assert call_count >= 10

    def test_register_tools_for_path_single(self):
        mock_mem0_tools = MagicMock()
        mock_mem0_tools.add_memory_tool = MagicMock()
        mock_mem0_tools.search_memory_tool = MagicMock()
        mock_mem0_tools.get_user_memories_tool = MagicMock()

        mock_fetching = MagicMock()
        mock_fetching.get_page = MagicMock()
        mock_fetching.render_html = MagicMock()

        mock_search = MagicMock()
        mock_search.search_web = MagicMock()
        mock_search.wikipedia_search = MagicMock()
        mock_search.search_metrics = MagicMock()

        mock_utils = MagicMock()
        mock_utils.health = MagicMock()
        mock_utils.current_datetime = MagicMock()

        mock_advanced = MagicMock()
        mock_advanced.create_chart_tool = MagicMock()
        mock_advanced.run_javascript = MagicMock()

        with (
            patch("web_mcp.server.FastMCP"),
            patch.dict(
                sys.modules,
                {
                    "web_mcp.mem0.tools": mock_mem0_tools,
                    "web_mcp.tools.fetching": mock_fetching,
                    "web_mcp.tools.search": mock_search,
                    "web_mcp.tools.utils": mock_utils,
                    "web_mcp.tools.advanced": mock_advanced,
                },
            ),
            patch("web_mcp.server.gather_knowledge"),
            patch("web_mcp.server.search_knowledge"),
            patch("web_mcp.server.manage_knowledge_collection"),
            patch("web_mcp.server.ToolAnnotations"),
        ):
            from web_mcp.server import register_tools_for_path

            mock_mcp = MagicMock()
            register_tools_for_path(mock_mcp, ["health"])

            mock_mcp.add_tool.assert_called()

    def test_register_tools_for_path_multiple(self):
        mock_mem0_tools = MagicMock()
        mock_mem0_tools.add_memory_tool = MagicMock()
        mock_mem0_tools.search_memory_tool = MagicMock()
        mock_mem0_tools.get_user_memories_tool = MagicMock()

        mock_fetching = MagicMock()
        mock_fetching.get_page = MagicMock()
        mock_fetching.render_html = MagicMock()

        mock_search = MagicMock()
        mock_search.search_web = MagicMock()
        mock_search.wikipedia_search = MagicMock()
        mock_search.search_metrics = MagicMock()

        mock_utils = MagicMock()
        mock_utils.health = MagicMock()
        mock_utils.current_datetime = MagicMock()

        mock_advanced = MagicMock()
        mock_advanced.create_chart_tool = MagicMock()
        mock_advanced.run_javascript = MagicMock()

        with (
            patch("web_mcp.server.FastMCP"),
            patch.dict(
                sys.modules,
                {
                    "web_mcp.mem0.tools": mock_mem0_tools,
                    "web_mcp.tools.fetching": mock_fetching,
                    "web_mcp.tools.search": mock_search,
                    "web_mcp.tools.utils": mock_utils,
                    "web_mcp.tools.advanced": mock_advanced,
                },
            ),
            patch("web_mcp.server.gather_knowledge"),
            patch("web_mcp.server.search_knowledge"),
            patch("web_mcp.server.manage_knowledge_collection"),
            patch("web_mcp.server.ToolAnnotations"),
        ):
            from web_mcp.server import register_tools_for_path

            mock_mcp = MagicMock()
            register_tools_for_path(mock_mcp, ["health", "current_datetime"])

            assert mock_mcp.add_tool.call_count >= 2

    def test_register_tools_for_path_unknown(self):
        mock_mem0_tools = MagicMock()
        mock_mem0_tools.add_memory_tool = MagicMock()
        mock_mem0_tools.search_memory_tool = MagicMock()
        mock_mem0_tools.get_user_memories_tool = MagicMock()

        mock_fetching = MagicMock()
        mock_fetching.get_page = MagicMock()
        mock_fetching.render_html = MagicMock()

        mock_search = MagicMock()
        mock_search.search_web = MagicMock()
        mock_search.wikipedia_search = MagicMock()
        mock_search.search_metrics = MagicMock()

        mock_utils = MagicMock()
        mock_utils.health = MagicMock()
        mock_utils.current_datetime = MagicMock()

        mock_advanced = MagicMock()
        mock_advanced.create_chart_tool = MagicMock()
        mock_advanced.run_javascript = MagicMock()

        with (
            patch("web_mcp.server.FastMCP"),
            patch.dict(
                sys.modules,
                {
                    "web_mcp.mem0.tools": mock_mem0_tools,
                    "web_mcp.tools.fetching": mock_fetching,
                    "web_mcp.tools.search": mock_search,
                    "web_mcp.tools.utils": mock_utils,
                    "web_mcp.tools.advanced": mock_advanced,
                },
            ),
            patch("web_mcp.server.gather_knowledge"),
            patch("web_mcp.server.search_knowledge"),
            patch("web_mcp.server.manage_knowledge_collection"),
            patch("web_mcp.server.ToolAnnotations"),
            patch("web_mcp.server.logger") as mock_logger,
        ):
            from web_mcp.server import register_tools_for_path

            mock_mcp = MagicMock()
            register_tools_for_path(mock_mcp, ["unknown_tool"])

            mock_logger.warning.assert_called()
            assert "Unknown tool" in str(mock_logger.warning.call_args)


class TestCreateDefaultMCP:
    def test_create_default_mcp(self):
        from web_mcp.server import create_default_mcp

        with (
            patch("web_mcp.server.create_auth_config") as mock_auth,
            patch("web_mcp.server.FastMCP") as mock_mcp_class,
        ):
            mock_auth.return_value = (None, None)
            mock_mcp = MagicMock()
            mock_mcp_class.return_value = mock_mcp

            result = create_default_mcp()

            assert result is mock_mcp
            mock_mcp_class.assert_called_once()
            call_kwargs = mock_mcp_class.call_args[1]
            assert call_kwargs["name"] == "web-browsing"
            assert call_kwargs["host"] == "0.0.0.0"
            assert call_kwargs["port"] == 8000


class TestMain:
    def test_main_stdio_mode(self):
        with (
            patch("web_mcp.server.mcp") as mock_mcp,
            patch("web_mcp.server.SERVER_HOST", "0.0.0.0"),
            patch("web_mcp.server.SERVER_PORT", 8000),
        ):
            from web_mcp.server import main

            main()

            mock_mcp.run.assert_called_once()

    def test_main_http_mode(self):
        with (
            patch("web_mcp.server.mcp") as mock_mcp,
            patch("web_mcp.server.SERVER_HOST", "0.0.0.0"),
            patch("web_mcp.server.SERVER_PORT", 8000),
        ):
            sys.argv = ["web_mcp.server", "--http"]
            from web_mcp.server import main

            main()

            mock_mcp.run.assert_called_once()
            call_kwargs = mock_mcp.run.call_args[1]
            assert call_kwargs["transport"] == "streamable-http"

    def test_main_sse_mode(self):
        with (
            patch("web_mcp.server.mcp") as mock_mcp,
            patch("web_mcp.server.SERVER_HOST", "0.0.0.0"),
            patch("web_mcp.server.SERVER_PORT", 8000),
        ):
            sys.argv = ["web_mcp.server", "--sse"]
            from web_mcp.server import main

            main()

            mock_mcp.run.assert_called_once()
            call_kwargs = mock_mcp.run.call_args[1]
            assert call_kwargs["transport"] == "sse"

    def test_main_streamable_http_mode(self):
        with (
            patch("web_mcp.server.mcp") as mock_mcp,
            patch("web_mcp.server.SERVER_HOST", "0.0.0.0"),
            patch("web_mcp.server.SERVER_PORT", 8000),
        ):
            sys.argv = ["web_mcp.server", "--streamable-http"]
            from web_mcp.server import main

            main()

            mock_mcp.run.assert_called_once()
            call_kwargs = mock_mcp.run.call_args[1]
            assert call_kwargs["transport"] == "streamable-http"


class TestLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_starts_and_stops_cleanup(self):
        with (
            patch("web_mcp.server.start_cleanup_task") as mock_start,
            patch("web_mcp.server.stop_cleanup_task") as mock_stop,
        ):
            from web_mcp.server import lifespan

            async with lifespan(MagicMock()):
                mock_start.assert_called_once()

            mock_stop.assert_called_once()


class TestServedRoutes:
    @pytest.mark.asyncio
    async def test_serve_stored_content_valid(self):
        with patch("web_mcp.server.get_content_store") as mock_store_getter:
            mock_store = MagicMock()
            mock_store.get.return_value = MagicMock(
                content="stored content", content_type="text/html", token="correct-token"
            )
            mock_store_getter.return_value = mock_store

            from web_mcp.server import serve_stored_content

            mock_request = MagicMock()
            mock_request.path_params = {"content_id": "abc123"}
            mock_request.query_params = {"token": "correct-token"}

            response = await serve_stored_content(mock_request)
            assert response is not None

    @pytest.mark.asyncio
    async def test_serve_stored_content_invalid_id(self):
        from web_mcp.server import serve_stored_content

        mock_request = MagicMock()
        mock_request.path_params = {"content_id": "invalid id!"}

        response = await serve_stored_content(mock_request)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_serve_stored_content_not_found(self):
        with patch("web_mcp.server.get_content_store") as mock_store_getter:
            mock_store = MagicMock()
            mock_store.get.return_value = None
            mock_store_getter.return_value = mock_store

            from web_mcp.server import serve_stored_content

            mock_request = MagicMock()
            mock_request.path_params = {"content_id": "abc123"}
            mock_request.query_params = {"token": "any"}

            response = await serve_stored_content(mock_request)
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_serve_stored_content_unauthorized(self):
        with patch("web_mcp.server.get_content_store") as mock_store_getter:
            mock_store = MagicMock()
            mock_store.get.return_value = MagicMock(
                content="content", content_type="text/html", token="correct-token"
            )
            mock_store_getter.return_value = mock_store

            from web_mcp.server import serve_stored_content

            mock_request = MagicMock()
            mock_request.path_params = {"content_id": "abc123"}
            mock_request.query_params = {"token": "wrong-token"}

            response = await serve_stored_content(mock_request)
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_serve_chart_image_valid(self):
        with patch("web_mcp.server.get_content_store") as mock_store_getter:
            mock_store = MagicMock()
            mock_store.get.return_value = MagicMock(
                content=b"png data", content_type="image/png", token="correct-token"
            )
            mock_store_getter.return_value = mock_store

            from web_mcp.server import serve_chart_image

            mock_request = MagicMock()
            mock_request.path_params = {"content_id": "img123.png"}
            mock_request.query_params = {"token": "correct-token"}

            response = await serve_chart_image(mock_request)
            assert response is not None

    @pytest.mark.asyncio
    async def test_serve_chart_image_invalid(self):
        from web_mcp.server import serve_chart_image

        mock_request = MagicMock()
        mock_request.path_params = {"content_id": "invalid!"}
        mock_request.query_params = {"token": "any"}

        response = await serve_chart_image(mock_request)
        assert response.status_code == 400


class TestKnowledgeTools:
    @pytest.mark.asyncio
    async def test_gather_knowledge_success(self, mock_mem0):
        with (
            patch("web_mcp.knowledge.validation.validate_topic_width") as mock_validate,
            patch("web_mcp.knowledge.gather_knowledge") as mock_gather,
        ):
            mock_validate.return_value = {"valid": True}
            mock_result = MagicMock()
            mock_result.summary.return_value = "Gathered 5 facts"
            mock_gather.return_value = mock_result

            from web_mcp.server import gather_knowledge

            result = await gather_knowledge("Python programming")
            assert "Gathered 5 facts" in result

    @pytest.mark.asyncio
    async def test_gather_knowledge_invalid_topic(self, mock_mem0):
        with patch("web_mcp.knowledge.validation.validate_topic_width") as mock_validate:
            mock_validate.return_value = {
                "valid": False,
                "issues": ["Topic too broad"],
            }

            from web_mcp.server import gather_knowledge

            result = await gather_knowledge("Python")
            assert "Topic validation issues" in result

    @pytest.mark.asyncio
    async def test_search_knowledge_no_results(self, mock_mem0):
        with patch("web_mcp.mem0.mem0_manager") as mock_manager:
            mock_memory = MagicMock()
            mock_memory.search.return_value = []
            mock_manager.get_memory.return_value = mock_memory

            from web_mcp.server import search_knowledge

            result = await search_knowledge("nonexistent query")
            assert "No knowledge found" in result

    @pytest.mark.asyncio
    async def test_search_knowledge_with_results(self, mock_mem0):
        with patch("web_mcp.mem0.mem0_manager") as mock_manager:
            mock_memory = MagicMock()
            mock_memory.search.return_value = [
                {
                    "memory": "Fact about Python",
                    "metadata": {
                        "confidence": 0.95,
                        "source_url": "https://python.org",
                        "category": "language",
                    },
                }
            ]
            mock_manager.get_memory.return_value = mock_memory

            from web_mcp.server import search_knowledge

            result = await search_knowledge("Python")
            assert "Fact about Python" in result
            assert "0.95" in result

    @pytest.mark.asyncio
    async def test_manage_knowledge_status(self, mock_mem0):
        with patch("web_mcp.mem0.mem0_manager") as mock_manager:
            mock_memory = MagicMock()
            mock_memory.get_all.return_value = {
                "results": [
                    {"metadata": {"category": "api", "source_url": "https://example.com"}},
                    {"metadata": {"category": "security", "source_url": "https://example.com"}},
                    {"metadata": {"category": "api", "source_url": "https://other.com"}},
                ]
            }
            mock_manager.get_memory.return_value = mock_memory

            from web_mcp.server import manage_knowledge_collection

            result = await manage_knowledge_collection("status")
            assert "Knowledge Collection Status:" in result
            assert "Total facts: 3" in result
            assert "Unique sources: 2" in result

    @pytest.mark.asyncio
    async def test_manage_knowledge_clear(self, mock_mem0):
        with patch("web_mcp.mem0.mem0_manager") as mock_manager:
            mock_memory = MagicMock()
            mock_memory.get_all.return_value = {
                "results": [
                    {"id": "1", "metadata": {"type": "knowledge_fact"}},
                    {"id": "2", "metadata": {"type": "knowledge_fact"}},
                    {"id": "3", "metadata": {"type": "user_memory"}},
                ]
            }
            mock_manager.get_memory.return_value = mock_memory

            from web_mcp.server import manage_knowledge_collection

            result = await manage_knowledge_collection("clear")
            assert "Cleared 2 knowledge facts" in result

    @pytest.mark.asyncio
    async def test_manage_knowledge_cleanup(self, mock_mem0):
        with (
            patch("web_mcp.mem0.mem0_manager"),
            patch("web_mcp.config.get_config") as mock_config,
            patch("web_mcp.knowledge.cleanup.KnowledgeCleanupTask") as mock_task_class,
        ):
            mock_config.return_value = MagicMock(knowledge_ttl_days=30)
            mock_task = MagicMock()
            mock_task.run_once = AsyncMock(return_value="Cleaned 5 entries")
            mock_task_class.return_value = mock_task

            from web_mcp.server import manage_knowledge_collection

            result = await manage_knowledge_collection("cleanup")
            assert "Cleanup result:" in result

    @pytest.mark.asyncio
    async def test_manage_knowledge_unknown_action(self, mock_mem0):
        with patch("web_mcp.mem0.mem0_manager") as mock_manager:
            mock_manager.get_memory.return_value = MagicMock()

            from web_mcp.server import manage_knowledge_collection

            result = await manage_knowledge_collection("invalid")
            assert "Unknown action" in result


class TestBuildAdminMode:
    def test_build_admin_mode(self):
        mock_mem0_tools = MagicMock()
        mock_mem0_tools.add_memory_tool = MagicMock()
        mock_mem0_tools.search_memory_tool = MagicMock()
        mock_mem0_tools.get_user_memories_tool = MagicMock()

        mock_fetching = MagicMock()
        mock_fetching.get_page = MagicMock()
        mock_fetching.render_html = MagicMock()

        mock_search = MagicMock()
        mock_search.search_web = MagicMock()
        mock_search.brave_search = MagicMock()
        mock_search.wikipedia_search = MagicMock()
        mock_search.wikipedia_research = MagicMock()
        mock_search.search_metrics = MagicMock()

        mock_utils = MagicMock()
        mock_utils.health = MagicMock()
        mock_utils.current_datetime = MagicMock()

        mock_advanced = MagicMock()
        mock_advanced.create_chart_tool = MagicMock()
        mock_advanced.run_javascript = MagicMock()

        mock_uvicorn = MagicMock()

        with (
            patch("web_mcp.path_routing.PathRouter") as mock_router,
            patch("web_mcp.server.create_default_mcp"),
            patch("web_mcp.admin.create_admin_routes") as mock_admin,
            patch("web_mcp.server.SERVER_HOST", "0.0.0.0"),
            patch("web_mcp.server.SERVER_PORT", 8000),
            patch.dict(
                sys.modules,
                {
                    "web_mcp.mem0.tools": mock_mem0_tools,
                    "web_mcp.tools.fetching": mock_fetching,
                    "web_mcp.tools.search": mock_search,
                    "web_mcp.tools.utils": mock_utils,
                    "web_mcp.tools.advanced": mock_advanced,
                    "uvicorn": mock_uvicorn,
                },
            ),
        ):
            mock_router_instance = MagicMock()
            mock_router.return_value = mock_router_instance
            mock_admin.return_value = ([], MagicMock(), MagicMock(), [])

            from web_mcp.server import build_admin_mode

            build_admin_mode()

            mock_uvicorn.run.assert_called_once()
