"""Unit tests for the LLM client with mocked HTTP calls."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_mcp.llm.client import LLMClient, LLMError, get_llm_client


class TestLLMClient:
    """Tests for LLMClient class."""

    @pytest.fixture
    def client(self):
        """Create an LLM client with mocked config."""
        with patch("web_mcp.llm.client.get_llm_config") as mock_config:
            config = MagicMock()
            config.api_url = "https://api.openai.com/v1"
            config.api_key = "test-key"
            config.model = "gpt-4o"
            config.embedding_model = "text-embedding-3-small"
            config.request_timeout = 60
            mock_config.return_value = config

            return LLMClient()

    @pytest.mark.asyncio
    async def test_embed_success(self, client):
        """Test successful embedding."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
            ]
        }

        with patch("web_mcp.llm.client.httpx.AsyncClient") as mock_client_class:
            mock_httpx_client = MagicMock()
            mock_httpx_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_httpx_client

            embeddings = await client.embed(["test text"])

            assert len(embeddings) == 1
            assert embeddings[0] == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_failure(self, client):
        """Test embedding failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("web_mcp.llm.client.httpx.AsyncClient") as mock_client_class:
            mock_httpx_client = MagicMock()
            mock_httpx_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_httpx_client

            with pytest.raises(LLMError) as exc_info:
                await client.embed(["test text"])

            assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_success(self, client):
        """Test successful chat completion."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": "Test response"}}]}

        with patch("web_mcp.llm.client.httpx.AsyncClient") as mock_client_class:
            mock_httpx_client = MagicMock()
            mock_httpx_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_httpx_client

            response = await client.chat([{"role": "user", "content": "Hello"}])

            assert response == "Test response"

    @pytest.mark.asyncio
    async def test_chat_failure(self, client):
        """Test chat completion failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("web_mcp.llm.client.httpx.AsyncClient") as mock_client_class:
            mock_httpx_client = MagicMock()
            mock_httpx_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_httpx_client

            with pytest.raises(LLMError) as exc_info:
                await client.chat([{"role": "user", "content": "Hello"}])

            assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_stream_success(self, client):
        """Test successful chat streaming."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        async def mock_aiter_lines():
            yield 'data: {"choices": [{"delta": {"content": "Test"}}]}'
            yield 'data: {"choices": [{"delta": {"content": " response"}}]}'
            yield "data: [DONE]"

        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("web_mcp.llm.client.httpx.AsyncClient") as mock_client_class:
            mock_httpx_client = MagicMock()
            mock_httpx_client.stream = MagicMock(return_value=mock_stream_ctx)
            mock_client_class.return_value = mock_httpx_client

            chunks = []
            async for chunk in client.chat_stream([{"role": "user", "content": "Hello"}]):
                chunks.append(chunk)

            assert "".join(chunks) == "Test response"

    @pytest.mark.asyncio
    async def test_chat_stream_failure(self, client):
        """Test chat streaming failure."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.aread = AsyncMock(return_value=b"Internal Server Error")

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("web_mcp.llm.client.httpx.AsyncClient") as mock_client_class:
            mock_httpx_client = MagicMock()
            mock_httpx_client.stream = MagicMock(return_value=mock_stream_ctx)
            mock_client_class.return_value = mock_httpx_client

            with pytest.raises(LLMError) as exc_info:
                async for _ in client.chat_stream([{"role": "user", "content": "Hello"}]):
                    pass

            assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_close_client(self, client):
        """Test closing the client."""
        with patch("web_mcp.llm.client.httpx.AsyncClient") as mock_client_class:
            mock_httpx_client = MagicMock()
            mock_httpx_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_httpx_client

            await client._get_client()

            await client.close()

            mock_httpx_client.aclose.assert_called_once()


class TestGetLlmClient:
    """Tests for get_llm_client function."""

    def test_get_llm_client_singleton(self):
        """Test that get_llm_client returns a singleton."""
        with patch("web_mcp.llm.client.get_llm_config"):
            client1 = get_llm_client()
            client2 = get_llm_client()

            assert client1 is client2

    def test_get_llm_client_creates_new_if_none(self):
        """Test that a new client is created if none exists."""
        with patch("web_mcp.llm.client.get_llm_config"):
            # Clear the global client
            import web_mcp.llm.client as client_module

            client_module._client = None

            result = get_llm_client()

            assert isinstance(result, LLMClient)
