"""Unit tests for the searxng module with mocked HTTP calls."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from web_mcp.searxng import SearXNGError, search, get_searxng_url


class TestGetSearxngUrl:
    """Tests for get_searxng_url function."""

    def test_get_searxng_url_configured(self):
        """Test getting configured SearXNG URL."""
        with patch.dict("os.environ", {"WEB_MCP_SEARXNG_URL": "http://localhost:8080"}):
            url = get_searxng_url()
            assert url == "http://localhost:8080"

    def test_get_searxng_url_not_configured(self):
        """Test when SearXNG is not configured."""
        import os
        env_copy = os.environ.copy()
        env_copy.pop("WEB_MCP_SEARXNG_URL", None)
        with patch.dict("os.environ", env_copy, clear=True):
            url = get_searxng_url()
            assert url is None

    def test_get_searxng_url_empty(self):
        """Test empty SearXNG URL."""
        with patch.dict("os.environ", {"WEB_MCP_SEARXNG_URL": ""}):
            url = get_searxng_url()
            assert url == ""


class TestSearch:
    """Tests for search function."""

    @pytest.mark.asyncio
    async def test_search_success(self):
        """Test successful search."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "snippet": "This is a test snippet",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch.dict("os.environ", {"WEB_MCP_SEARXNG_URL": "http://localhost:8080"}):
                results = await search("test query", max_results=5)

                assert len(results) == 1
                assert results[0]["title"] == "Test Result"
                assert results[0]["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_search_not_configured(self):
        """Test search when SearXNG is not configured."""
        import os
        env_copy = os.environ.copy()
        env_copy.pop("WEB_MCP_SEARXNG_URL", None)
        with patch.dict("os.environ", env_copy, clear=True):
            with pytest.raises(SearXNGError) as exc_info:
                await search("test query")

            assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_timeout(self):
        """Test search with timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(
                side_effect=Exception("Request timed out")
            )
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch.dict("os.environ", {"WEB_MCP_SEARXNG_URL": "http://localhost:8080"}):
                with pytest.raises(SearXNGError) as exc_info:
                    await search("test query")

                assert "Request timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_http_error(self):
        """Test search with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(
                side_effect=Exception("HTTP error 500")
            )
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch.dict("os.environ", {"WEB_MCP_SEARXNG_URL": "http://localhost:8080"}):
                with pytest.raises(SearXNGError) as exc_info:
                    await search("test query")

                assert "500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_with_published_date(self):
        """Test search with published date in response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "snippet": "Snippet text",
                    "publishedDate": "2024-01-01",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch.dict("os.environ", {"WEB_MCP_SEARXNG_URL": "http://localhost:8080"}):
                results = await search("test query")

                assert results[0]["published_date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_search_with_score(self):
        """Test search with score in response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "snippet": "Snippet text",
                    "score": 0.95,
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch.dict("os.environ", {"WEB_MCP_SEARXNG_URL": "http://localhost:8080"}):
                results = await search("test query")

                assert results[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        """Test search with no results."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch.dict("os.environ", {"WEB_MCP_SEARXNG_URL": "http://localhost:8080"}):
                results = await search("test query")

                assert results == []

    @pytest.mark.asyncio
    async def test_search_snippet_fallback(self):
        """Test search snippet fallback to content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "Content fallback",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with patch.dict("os.environ", {"WEB_MCP_SEARXNG_URL": "http://localhost:8080"}):
                results = await search("test query")

                assert results[0]["snippet"] == "Content fallback"
