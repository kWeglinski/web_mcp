"""Unit tests for tool registration functions in server module."""

from unittest.mock import MagicMock, patch

from web_mcp.server import TOOL_REGISTRY, register_all_tools, register_tools_for_path


class TestRegisterAllTools:
    """Tests for register_all_tools function."""

    def test_register_all_tools(self, mock_mem0):
        """Test verify all 14 tools registered on MCP instance."""
        mock_mcp = MagicMock()

        with patch("web_mcp.server._register_tool") as mock_register:
            register_all_tools(mock_mcp)

            # Should be called 14 times for 14 tools
            assert mock_register.call_count == 14

    def test_register_all_tools_calls_add_tool(self, mock_mem0):
        """Test that register_all_tools actually calls mcp.add_tool for each tool."""
        mock_mcp = MagicMock()

        register_all_tools(mock_mcp)

        # add_tool should be called 14 times
        assert mock_mcp.add_tool.call_count == 14


class TestRegisterToolsForPath:
    """Tests for register_tools_for_path function."""

    def test_register_tools_for_path(self, mock_mem0):
        """Test verify only specified tools registered."""
        mock_mcp = MagicMock()

        register_tools_for_path(mock_mcp, ["get_page", "health"])

        # Only 2 tools should be registered
        assert mock_mcp.add_tool.call_count == 2

    def test_register_tools_for_path_single_tool(self, mock_mem0):
        """Test registering a single tool."""
        mock_mcp = MagicMock()

        register_tools_for_path(mock_mcp, ["search_web"])

        assert mock_mcp.add_tool.call_count == 1

    def test_register_tools_for_path_unknown(self, mock_mem0):
        """Test warns on unknown tool, doesn't crash."""
        mock_mcp = MagicMock()

        # Should not raise, just warn and skip
        register_tools_for_path(mock_mcp, ["get_page", "nonexistent_tool", "health"])

        # Only 2 valid tools registered, 1 skipped
        assert mock_mcp.add_tool.call_count == 2


class TestToolRegistry:
    """Tests for TOOL_REGISTRY contents."""

    def test_tool_registry_has_14_tools(self):
        """Test verify TOOL_REGISTRY has exactly 14 entries."""
        assert len(TOOL_REGISTRY) == 14

    def test_tool_registry_has_expected_tools(self):
        """Test verify expected tool names are present."""
        expected_tools = {
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
        }
        assert set(TOOL_REGISTRY.keys()) == expected_tools

    def test_tool_registry_entries_have_required_fields(self):
        """Test each tool entry has name, description, is_read_only, module."""
        for name, entry in TOOL_REGISTRY.items():
            assert "name" in entry
            assert "description" in entry
            assert "is_read_only" in entry
            assert "module" in entry
            assert entry["name"] == name

    def test_tool_registry_read_only_tools(self):
        """Test read-only tools are marked correctly."""
        read_only_tools = {
            "get_page",
            "render_html",
            "search_web",
            "brave_search",
            "search_metrics",
            "health",
            "current_datetime",
            "search_memory",
            "get_user_memories",
        }
        for name in read_only_tools:
            assert TOOL_REGISTRY[name]["is_read_only"] is True

    def test_tool_registry_write_tools(self):
        """Test write tools are marked correctly."""
        write_tools = {"create_chart_tool", "run_javascript", "add_memory"}
        for name in write_tools:
            assert TOOL_REGISTRY[name]["is_read_only"] is False

    def test_tool_registry_destructive_tools(self):
        """Test destructive tools are marked correctly."""
        assert TOOL_REGISTRY["run_javascript"].get("destructive") is True
        # Other tools should not have destructive flag or it should be False
        for name, entry in TOOL_REGISTRY.items():
            if name != "run_javascript":
                assert entry.get("destructive") is not True
