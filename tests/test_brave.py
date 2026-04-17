"""Tests for Brave Search module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_mcp.brave import (
    BraveSearchError,
    get_brave_api_key,
    parse_brave_to_markdown,
    remove_html_tags,
    search,
)


class TestGetBraveApiKey:
    def test_returns_none_when_not_set(self, monkeypatch):
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        assert get_brave_api_key() is None

    def test_returns_key_when_set(self, monkeypatch):
        monkeypatch.setenv("BRAVE_API_KEY", "test-key-123")
        assert get_brave_api_key() == "test-key-123"


class TestRemoveHtmlTags:
    def test_removes_simple_tags(self):
        assert remove_html_tags("<p>Hello World</p>") == "Hello World"

    def test_removes_nested_tags(self):
        assert remove_html_tags("<div><span>Hello</span> <b>World</b></div>") == "Hello World"

    def test_handles_none(self):
        assert remove_html_tags(None) == ""

    def test_handles_empty_string(self):
        assert remove_html_tags("") == ""

    def test_normalizes_whitespace(self):
        assert remove_html_tags("<p>Hello\n\nWorld</p>") == "Hello World"


class TestParseBraveToMarkdown:
    def test_empty_results(self):
        data = {"web": {"results": []}}
        result = parse_brave_to_markdown(data, "test query")
        assert result == "*No search results found*"

    def test_single_result(self):
        data = {
            "web": {
                "results": [
                    {
                        "title": "Test Title",
                        "url": "https://example.com",
                        "description": "Test description",
                        "page_age": "2024-01-15",
                        "profile": {"name": "Example Site"},
                    }
                ]
            }
        }
        result = parse_brave_to_markdown(data, "test query")
        assert "Test Title" in result
        assert "https://example.com" in result
        assert "Test description" in result
        assert "2024-01-15" in result
        assert "Example Site" in result

    def test_truncates_long_content(self):
        long_desc = "x" * 2000
        data = {
            "web": {
                "results": [
                    {
                        "title": "Test",
                        "url": "https://example.com",
                        "description": long_desc,
                    }
                ]
            }
        }
        result = parse_brave_to_markdown(data, "test", max_content_length=100)
        assert len(result) < len(long_desc) + 500

    def test_max_results_limit(self):
        data = {
            "web": {
                "results": [
                    {
                        "title": f"Result {i}",
                        "url": f"https://example.com/{i}",
                        "description": f"Desc {i}",
                    }
                    for i in range(20)
                ]
            }
        }
        result = parse_brave_to_markdown(data, "test", max_results=5)
        assert result.count("### Result #") == 5


class TestSearch:
    @pytest.mark.asyncio
    async def test_raises_error_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        with pytest.raises(BraveSearchError, match="BRAVE_API_KEY environment variable not set"):
            await search("test query")

    @pytest.mark.asyncio
    async def test_successful_search(self, monkeypatch):
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {
                        "title": "Test Result",
                        "url": "https://example.com",
                        "description": "Test description",
                        "page_age": "2024-01-01",
                    }
                ]
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            results = await search("test query")

        assert len(results) == 1
        assert results[0]["title"] == "Test Result"
        assert results[0]["url"] == "https://example.com"
        assert results[0]["snippet"] == "Test description"

    @pytest.mark.asyncio
    async def test_handles_401_error(self, monkeypatch):
        monkeypatch.setenv("BRAVE_API_KEY", "invalid-key")

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            with pytest.raises(BraveSearchError, match="Invalid Brave API key"):
                await search("test query")

    @pytest.mark.asyncio
    async def test_handles_429_rate_limit(self, monkeypatch):
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            with pytest.raises(BraveSearchError, match="rate limit exceeded"):
                await search("test query")

    @pytest.mark.asyncio
    async def test_handles_timeout(self, monkeypatch):
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException("timeout")
            )
            with pytest.raises(BraveSearchError, match="timed out"):
                await search("test query")
