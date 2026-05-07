"""Tests for time_range parameter in SearXNG search and MCP tools."""

from unittest.mock import AsyncMock, MagicMock, patch


async def test_search_passes_time_range_to_searxng():
    """Verify time_range is passed through to the SearXNG JSON API params."""
    from web_mcp.searxng import search

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"title": "Test Result", "url": "https://example.com", "content": "test content"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("web_mcp.searxng.get_searxng_url", return_value="http://test-searxng.local"):
        with patch("web_mcp.searxng._is_blacklisted", return_value=False):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await search("test query", max_results=5, time_range="week")

    assert len(result) == 1
    mock_client.get.assert_called_once()
    call_kwargs = mock_client.get.call_args
    params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
    assert params["time_range"] == "week"


async def test_search_without_time_range_works_as_before():
    """Verify search works without time_range (default behavior unchanged)."""
    from web_mcp.searxng import search

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {"title": "Test Result", "url": "https://example.com", "content": "test content"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("web_mcp.searxng.get_searxng_url", return_value="http://test-searxng.local"):
        with patch("web_mcp.searxng._is_blacklisted", return_value=False):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await search("test query", max_results=5)

    assert len(result) == 1
    mock_client.get.assert_called_once()
    call_kwargs = mock_client.get.call_args
    params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
    assert "time_range" not in params


async def test_search_web_tool_accepts_time_range_param():
    """Verify search_web MCP tool accepts and passes time_range parameter."""
    from web_mcp.server import search_web

    mock_results = [
        {
            "title": "Test Result",
            "url": "https://example.com",
            "snippet": "test content",
            "score": 0.9,
        }
    ]

    with patch("web_mcp.server.search", new_callable=AsyncMock) as mock_search:
        with patch("web_mcp.server.deduplicate_results", return_value=mock_results):
            mock_search.return_value = mock_results

            result = await search_web(query="test query", time_range="day")

    mock_search.assert_called_once_with("test query", 30, time_range="day")
    assert "Test Result" in result


async def test_search_web_tool_without_time_range():
    """Verify search_web works without time_range (default behavior)."""
    from web_mcp.server import search_web

    mock_results = [
        {
            "title": "Test Result",
            "url": "https://example.com",
            "snippet": "test content",
            "score": 0.9,
        }
    ]

    with patch("web_mcp.server.search", new_callable=AsyncMock) as mock_search:
        with patch("web_mcp.server.deduplicate_results", return_value=mock_results):
            mock_search.return_value = mock_results

            await search_web(query="test query")

    assert mock_search.called
    call_kwargs = mock_search.call_args.kwargs
    assert "time_range" in call_kwargs


async def test_brave_search_passes_time_range():
    """Verify brave_search tool passes time_range to Brave API."""
    from web_mcp.server import brave_search

    mock_results = [
        {
            "title": "Brave Result",
            "url": "https://example.com",
            "snippet": "test content",
        }
    ]

    with patch("web_mcp.brave.search", new_callable=AsyncMock) as mock_brave:
        with patch("web_mcp.server.deduplicate_results", return_value=mock_results):
            mock_brave.return_value = mock_results

            await brave_search(query="test query", time_range="month")

    mock_brave.assert_called_once_with("test query", max_results=5, time_range="month")


async def test_search_instance_html_includes_time_range():
    """Verify HTML fallback search URL includes time_range parameter."""
    from web_mcp.searxng import _search_instance_html

    mock_fetch = AsyncMock(return_value="<html><body>test results</body></html>")

    with patch("web_mcp.playwright_fetcher.fetch_with_playwright", mock_fetch):
        try:
            await _search_instance_html("http://127.0.0.1", "query test", 5, time_range="day")
        except Exception:
            pass

    mock_fetch.assert_called_once()
    call_args = mock_fetch.call_args
    url_arg = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
    assert "time=day" in url_arg


async def test_brave_freshness_mapping():
    """Verify Brave time_range to freshness parameter mapping."""
    from web_mcp.brave import search as brave_search

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"web": {"results": []}}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("web_mcp.brave.get_brave_api_key", return_value="fake-key"):
        with patch("httpx.AsyncClient", return_value=mock_client):
            try:
                await brave_search("test", max_results=5, time_range="week")
            except Exception:
                pass

    call_kwargs = mock_client.get.call_args
    params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
    assert params["freshness"] == "PW"
