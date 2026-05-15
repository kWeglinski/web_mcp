"""Unit tests for mem0 module."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# Mock mem0 before importing web_mcp.mem0
mock_mem0 = ModuleType("mem0")
mock_mem0.Memory = MagicMock
sys.modules["mem0"] = mock_mem0

from web_mcp.mem0 import Mem0Manager, mem0_manager  # noqa: E402


class TestMem0Manager:
    @patch("web_mcp.mem0.get_config")
    def test_get_memory_initializes_once(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            mem1 = manager.get_memory()
            mem2 = manager.get_memory()

            assert mem1 is mem2
            mock_memory_class.from_config.assert_called_once()

    @patch("web_mcp.mem0.get_config")
    def test_get_memory_uses_env_vars(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            manager.get_memory()

            call_kwargs = mock_memory_class.from_config.call_args[0][0]
            assert call_kwargs["llm"]["config"]["model"] == "llama3:8b"
            assert call_kwargs["llm"]["config"]["base_url"] == "http://host.docker.internal:1234/v1"
            assert call_kwargs["llm"]["config"]["api_key"] == "local-secret"
            assert call_kwargs["embedder"]["provider"] == "openai"
            assert call_kwargs["embedder"]["config"]["model"] == "text-embedding-3-small"
            assert call_kwargs["embedder"]["config"]["base_url"] == "http://host.docker.internal:1234/v1"
            assert call_kwargs["embedder"]["config"]["api_key"] == "local-secret"
            assert call_kwargs["vector_store"]["config"]["path"] == "/app/chroma_db"
            assert call_kwargs["vector_store"]["config"]["collection_name"] == "mcp_memories"

    @patch("web_mcp.mem0.get_config")
    def test_add_with_metadata(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_instance.add.return_value = {"results": [{"id": "mem1", "memory": "test"}]}
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            result = manager.add_with_metadata(
                "Fact about Python",
                {"source_url": "https://example.com", "category": "programming"},
            )

            mock_memory_instance.add.assert_called_once_with(
                messages="Fact about Python",
                user_id="knowledge",
                metadata={"source_url": "https://example.com", "category": "programming"},
            )
            assert result == {"results": [{"id": "mem1", "memory": "test"}]}

    @patch("web_mcp.mem0.get_config")
    def test_add_with_string_messages(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            manager.add("Simple message", user_id="user1")

            mock_memory_instance.add.assert_called_once_with(
                messages="Simple message",
                user_id="user1",
                metadata=None,
            )

    @patch("web_mcp.mem0.get_config")
    def test_add_with_dict_messages(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            manager.add([{"role": "user", "content": "Hello"}], user_id="user2")

            mock_memory_instance.add.assert_called_once_with(
                messages=[{"role": "user", "content": "Hello"}],
                user_id="user2",
                metadata=None,
            )

    @patch("web_mcp.mem0.get_config")
    def test_add_uses_default_user_id(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            manager.add("Test message")

            mock_memory_instance.add.assert_called_once_with(
                messages="Test message",
                user_id="knowledge",
                metadata=None,
            )

    @patch("web_mcp.mem0.get_config")
    def test_add_message_alias(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            manager.add("Test", message="Alias test")

            mock_memory_instance.add.assert_called_once()
            call_kwargs = mock_memory_instance.add.call_args[1]
            assert call_kwargs["messages"] == "Alias test"

    @patch("web_mcp.mem0.get_config")
    def test_list_memories(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_instance.get_all.return_value = {
                "results": [
                    {"id": "mem1", "memory": "Fact 1"},
                    {"id": "mem2", "memory": "Fact 2"},
                ]
            }
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            result = manager.list(user_id="knowledge")

            assert len(result) == 2
            assert result[0]["memory"] == "Fact 1"

    @patch("web_mcp.mem0.get_config")
    def test_list_memories_returns_empty(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_instance.get_all.return_value = {"results": []}
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            result = manager.list()
            assert result == []

    @patch("web_mcp.mem0.get_config")
    def test_list_memories_top_k(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            manager.list(top_k=50)

            mock_memory_instance.get_all.assert_called_once()
            call_kwargs = mock_memory_instance.get_all.call_args[1]
            assert call_kwargs["top_k"] == 50

    @patch("web_mcp.mem0.get_config")
    def test_delete_memory(self, mock_config):
        mock_config.return_value = MagicMock()

        with patch("web_mcp.mem0.Memory") as mock_memory_class:
            mock_memory_instance = MagicMock()
            mock_memory_class.from_config.return_value = mock_memory_instance

            manager = Mem0Manager()
            manager.delete("mem123")

            mock_memory_instance.delete.assert_called_once_with("mem123")


class TestMem0ManagerSingleton:
    def test_singleton_instance(self):
        assert mem0_manager is not None
        assert isinstance(mem0_manager, Mem0Manager)


class TestMem0ManagerWithEnvOverrides:
    @patch("web_mcp.mem0.get_config")
    def test_uses_env_var_for_llm_model(self, mock_config):
        import os

        mock_config.return_value = MagicMock()

        os.environ["WEB_MCP_MEM0_LLM_MODEL"] = "gpt-4"
        try:
            with patch("web_mcp.mem0.Memory") as mock_memory_class:
                mock_memory_instance = MagicMock()
                mock_memory_class.from_config.return_value = mock_memory_instance

                manager = Mem0Manager()
                manager.get_memory()

                call_kwargs = mock_memory_class.from_config.call_args[0][0]
                assert call_kwargs["llm"]["config"]["model"] == "gpt-4"
        finally:
            del os.environ["WEB_MCP_MEM0_LLM_MODEL"]

    @patch("web_mcp.mem0.get_config")
    def test_uses_env_var_for_base_url(self, mock_config):
        import os

        mock_config.return_value = MagicMock()

        os.environ["WEB_MCP_MEM0_BASE_URL"] = "http://custom:8080/v1"
        try:
            with patch("web_mcp.mem0.Memory") as mock_memory_class:
                mock_memory_instance = MagicMock()
                mock_memory_class.from_config.return_value = mock_memory_instance

                manager = Mem0Manager()
                manager.get_memory()

                call_kwargs = mock_memory_class.from_config.call_args[0][0]
                assert call_kwargs["llm"]["config"]["base_url"] == "http://custom:8080/v1"
        finally:
            del os.environ["WEB_MCP_MEM0_BASE_URL"]

    @patch("web_mcp.mem0.get_config")
    def test_uses_env_var_for_chroma_path(self, mock_config):
        import os

        mock_config.return_value = MagicMock()

        os.environ["WEB_MCP_MEM0_CHROMA_PATH"] = "/custom/path"
        try:
            with patch("web_mcp.mem0.Memory") as mock_memory_class:
                mock_memory_instance = MagicMock()
                mock_memory_class.from_config.return_value = mock_memory_instance

                manager = Mem0Manager()
                manager.get_memory()

                call_kwargs = mock_memory_class.from_config.call_args[0][0]
                assert call_kwargs["vector_store"]["config"]["path"] == "/custom/path"
        finally:
            del os.environ["WEB_MCP_MEM0_CHROMA_PATH"]
