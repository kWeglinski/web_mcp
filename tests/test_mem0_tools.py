"""Unit tests for mem0 tools module."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

mock_mem0 = ModuleType("mem0")
mock_mem0.Memory = MagicMock
sys.modules["mem0"] = mock_mem0

from web_mcp.mem0.tools import (  # noqa: E402
    MEM0_TOOLS,
    add_memory_tool,
    get_user_memories_tool,
    search_memory_tool,
)


class TestAddMemoryTool:

    @pytest.mark.asyncio
    async def test_add_memory_success(self):
        mock_memory = MagicMock()
        mock_memory.add.return_value = [{"memory": "test result"}]

        mock_manager = MagicMock()
        mock_manager.get_memory.return_value = mock_memory

        with (
            patch("web_mcp.mem0.tools.mem0_manager", mock_manager),
            patch("web_mcp.mem0.tools.get_current_user_id", return_value="42"),
        ):
            result = await add_memory_tool("test message")
            assert result == "Memory added successfully"
            mock_memory.add.assert_called_once_with("test message", user_id="42")

    @pytest.mark.asyncio
    async def test_add_memory_error(self):
        mock_memory = MagicMock()
        mock_memory.add.side_effect = Exception("API error")

        mock_manager = MagicMock()
        mock_manager.get_memory.return_value = mock_memory

        with (
            patch("web_mcp.mem0.tools.mem0_manager", mock_manager),
            patch("web_mcp.mem0.tools.get_current_user_id", return_value="42"),
        ):
            result = await add_memory_tool("test message")
            assert "API error" in result

    @pytest.mark.asyncio
    async def test_add_memory_no_user(self):
        with patch("web_mcp.mem0.tools.get_current_user_id", return_value=None):
            result = await add_memory_tool("test message")
            assert "No authenticated user" in result


class TestSearchMemoryTool:

    @pytest.mark.asyncio
    async def test_search_memory_success(self):
        mock_memory = MagicMock()
        mock_memory.search.return_value = [
            {"memory": "result1"},
            {"memory": "result2"},
        ]

        mock_manager = MagicMock()
        mock_manager.get_memory.return_value = mock_memory

        with (
            patch("web_mcp.mem0.tools.mem0_manager", mock_manager),
            patch("web_mcp.mem0.tools.get_current_user_id", return_value="42"),
        ):
            result = await search_memory_tool("query")
            assert "result1" in result
            assert "result2" in result
            mock_memory.search.assert_called_once_with("query", filters={"user_id": "42"})

    @pytest.mark.asyncio
    async def test_search_memory_no_user(self):
        with patch("web_mcp.mem0.tools.get_current_user_id", return_value=None):
            result = await search_memory_tool("query")
            assert "No authenticated user" in result


class TestGetUserMemoriesTool:

    @pytest.mark.asyncio
    async def test_get_user_memories_success(self):
        mock_memory = MagicMock()
        mock_memory.get_all.return_value = {
            "results": [
                {"memory": "mem1"},
                {"memory": "mem2"},
            ]
        }

        mock_manager = MagicMock()
        mock_manager.get_memory.return_value = mock_memory

        with (
            patch("web_mcp.mem0.tools.mem0_manager", mock_manager),
            patch("web_mcp.mem0.tools.get_current_user_id", return_value="42"),
        ):
            result = await get_user_memories_tool()
            assert "mem1" in result
            assert "mem2" in result
            mock_memory.get_all.assert_called_once_with(filters={"user_id": "42"})

    @pytest.mark.asyncio
    async def test_get_user_memories_no_user(self):
        with patch("web_mcp.mem0.tools.get_current_user_id", return_value=None):
            result = await get_user_memories_tool()
            assert "No authenticated user" in result


class TestMem0ToolsRegistry:

    def test_mem0_tools_registry(self):
        assert "add_memory" in MEM0_TOOLS
        assert "search_memory" in MEM0_TOOLS
        assert "get_user_memories" in MEM0_TOOLS
        assert len(MEM0_TOOLS) == 3
