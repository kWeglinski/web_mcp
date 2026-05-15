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

        with patch("web_mcp.mem0.tools.mem0_manager", mock_manager):
            result = await add_memory_tool("test_user", "test message")
            assert result == "Memory added successfully"
            mock_memory.add.assert_called_once_with("test message", user_id="test_user")

    @pytest.mark.asyncio
    async def test_add_memory_error(self):
        mock_memory = MagicMock()
        mock_memory.add.side_effect = Exception("API error")

        mock_manager = MagicMock()
        mock_manager.get_memory.return_value = mock_memory

        with patch("web_mcp.mem0.tools.mem0_manager", mock_manager):
            result = await add_memory_tool("test_user", "test message")
            assert "API error" in result


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

        with patch("web_mcp.mem0.tools.mem0_manager", mock_manager):
            result = await search_memory_tool("test_user", "query")
            assert result == [{"memory": "result1"}, {"memory": "result2"}]
            mock_memory.search.assert_called_once_with("query", user_id="test_user")


class TestGetUserMemoriesTool:

    @pytest.mark.asyncio
    async def test_get_user_memories_success(self):
        mock_memory = MagicMock()
        mock_memory.get_all.return_value = [
            {"memory": "mem1"},
            {"memory": "mem2"},
        ]

        mock_manager = MagicMock()
        mock_manager.get_memory.return_value = mock_memory

        with patch("web_mcp.mem0.tools.mem0_manager", mock_manager):
            result = await get_user_memories_tool("test_user")
            assert result == [{"memory": "mem1"}, {"memory": "mem2"}]
            mock_memory.get_all.assert_called_once_with(user_id="test_user")


class TestMem0ToolsRegistry:

    def test_mem0_tools_registry(self):
        assert "add_memory" in MEM0_TOOLS
        assert "search_memory" in MEM0_TOOLS
        assert "get_user_memories" in MEM0_TOOLS
        assert len(MEM0_TOOLS) == 3
