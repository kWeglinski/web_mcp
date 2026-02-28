"""Unit tests for the searxng module with mocked HTTP calls."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from web_mcp.searxng import (
    SearXNGError,
    search,
    get_searxng_url,
    parse_searxng_to_markdown,
    remove_html_tags,
    parse_date,
)


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


class TestRemoveHtmlTags:
    """Tests for remove_html_tags function."""

    def test_remove_html_tags_basic(self):
        """Test removing basic HTML tags."""
        text = "<p>Hello <b>world</b></p>"
        result = remove_html_tags(text)
        assert result == "Hello world"

    def test_remove_html_tags_with_entities(self):
        """Test with HTML entities preserved."""
        text = "<div>Text &amp; more</div>"
        result = remove_html_tags(text)
        assert result == "Text &amp; more"

    def test_remove_html_tags_whitespace_normalization(self):
        """Test whitespace normalization."""
        text = "<p>Line 1</p>\n\n<p>Line 2</p>"
        result = remove_html_tags(text)
        assert result == "Line 1 Line 2"

    def test_remove_html_tags_empty(self):
        """Test with empty string."""
        assert remove_html_tags("") == ""

    def test_remove_html_tags_none(self):
        """Test with None."""
        assert remove_html_tags(None) == ""


class TestParseDate:
    """Tests for parse_date function."""

    def test_parse_date_iso_with_z(self):
        """Test ISO date with Z suffix."""
        result = parse_date("2024-11-15T10:30:00Z")
        assert result == "2024-11-15"

    def test_parse_date_iso_with_timezone(self):
        """Test ISO date with timezone offset."""
        result = parse_date("2024-11-15T10:30:00+00:00")
        assert result == "2024-11-15"

    def test_parse_date_none(self):
        """Test with None input."""
        assert parse_date(None) == "Unknown"

    def test_parse_date_empty(self):
        """Test with empty string."""
        assert parse_date("") == "Unknown"

    def test_parse_date_invalid(self):
        """Test with invalid date string."""
        assert parse_date("not-a-date") == "Unknown"


class TestParseSearxngToMarkdown:
    """Tests for parse_searxng_to_markdown function."""

    def test_basic_conversion(self):
        """Test basic JSON to markdown conversion."""
        json_data = {
            "results": [
                {
                    "url": "https://example.com/article",
                    "title": "Test Article",
                    "content": "This is the content.",
                    "published_date": "2024-11-15T10:30:00Z",
                    "score": 0.95,
                    "engine": "google",
                }
            ]
        }
        result = parse_searxng_to_markdown(json_data, "test query")

        assert '# Search Results for: "test query"' in result
        assert "**Total Results:** 1" in result
        assert "### Result #1 (Score: 0.95)" in result
        assert "[Test Article](https://example.com/article)" in result
        assert "**Published:** 2024-11-15" in result
        assert "**Engine:** Google" in result
        assert "#### Key Findings" in result
        assert "This is the content." in result
        assert "[End of Result #1]" in result

    def test_empty_results(self):
        """Test with empty results."""
        json_data = {"results": []}
        result = parse_searxng_to_markdown(json_data, "test")
        assert result == "*No search results found*"

    def test_snippet_fallback(self):
        """Test fallback to snippet when content is missing."""
        json_data = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Test",
                    "snippet": "Snippet text",
                    "score": 0.8,
                    "engine": "bing",
                }
            ]
        }
        result = parse_searxng_to_markdown(json_data, "test")
        assert "Snippet text" in result

    def test_html_removal(self):
        """Test HTML tags are removed from content."""
        json_data = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Test",
                    "content": "<p>Bold <b>text</b></p>",
                    "score": 0.9,
                    "engine": "google",
                }
            ]
        }
        result = parse_searxng_to_markdown(json_data, "test")
        assert "<p>" not in result
        assert "<b>" not in result
        assert "Bold text" in result

    def test_sorting_by_score(self):
        """Test results are sorted by score descending."""
        json_data = {
            "results": [
                {"url": "https://a.com", "title": "A", "content": "A", "score": 0.5},
                {"url": "https://b.com", "title": "B", "content": "B", "score": 0.9},
                {"url": "https://c.com", "title": "C", "content": "C", "score": 0.7},
            ]
        }
        result = parse_searxng_to_markdown(json_data, "test")
        assert result.index("Result #1") < result.index("Result #2")
        assert "B" in result.split("Result #1")[1].split("Result #2")[0]

    def test_max_results_limit(self):
        """Test max_results parameter limits output."""
        json_data = {
            "results": [
                {"url": f"https://{i}.com", "title": str(i), "content": str(i), "score": i / 10}
                for i in range(1, 20)
            ]
        }
        result = parse_searxng_to_markdown(json_data, "test", max_results=5)
        assert "Result #5" in result
        assert "Result #6" not in result

    def test_content_truncation(self):
        """Test long content is truncated."""
        long_content = "x" * 2000
        json_data = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Test",
                    "content": long_content,
                    "score": 0.9,
                    "engine": "google",
                }
            ]
        }
        result = parse_searxng_to_markdown(json_data, "test", max_content_length=500)
        assert "..." in result
        assert len([line for line in result.split("\n") if "xxxxx" in line][0]) <= 510

    def test_bm25_score_normalization(self):
        """Test BM25 score is normalized when score is missing."""
        json_data = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Test",
                    "content": "Content",
                    "bm25_score": 14.4091,
                    "engine": "google",
                }
            ]
        }
        result = parse_searxng_to_markdown(json_data, "test")
        assert "(Score: 1.00)" in result

    def test_published_date_fallback(self):
        """Test publishedDate field is used as fallback."""
        json_data = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Test",
                    "content": "Content",
                    "publishedDate": "2024-01-15",
                    "score": 0.9,
                    "engine": "google",
                }
            ]
        }
        result = parse_searxng_to_markdown(json_data, "test")
        assert "**Published:** 2024-01-15" in result

    def test_missing_date_shows_unknown(self):
        """Test missing date shows Unknown."""
        json_data = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Test",
                    "content": "Content",
                    "score": 0.9,
                    "engine": "google",
                }
            ]
        }
        result = parse_searxng_to_markdown(json_data, "test")
        assert "**Published:** Unknown" in result

    def test_consistent_delimiters(self):
        """Test consistent delimiters between results."""
        json_data = {
            "results": [
                {"url": "https://a.com", "title": "A", "content": "A", "score": 0.9},
                {"url": "https://b.com", "title": "B", "content": "B", "score": 0.8},
            ]
        }
        result = parse_searxng_to_markdown(json_data, "test")
        assert result.count("[End of Result #") == 2
        assert result.count("---") >= 3
