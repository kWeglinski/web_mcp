"""Tests for WEB_MCP_SEARCH_PROVIDER configuration."""

import os
from unittest.mock import AsyncMock, patch


async def test_search_uses_brave_when_configured():
    """Verify search_web calls _search_brave when WEB_MCP_SEARCH_PROVIDER=brave."""
    with patch.dict(os.environ, {"WEB_MCP_SEARCH_PROVIDER": "brave"}):
        import importlib

        import web_mcp.tools._core as core_module

        importlib.reload(core_module)
        assert core_module._SEARCH_PROVIDER == "brave"

        import web_mcp.tools.search as search_module

        importlib.reload(search_module)

        mock_result = "*mocked brave result*"
        with patch.object(search_module, "_search_brave", new_callable=AsyncMock) as mock_brave:
            with patch.object(
                search_module, "_search_searxng", new_callable=AsyncMock
            ) as mock_searxng:
                mock_brave.return_value = mock_result

                result = await search_module.search_web(query="test query")

        assert result == mock_result
        mock_brave.assert_called_once()
        mock_searxng.assert_not_called()


async def test_search_uses_searxng_by_default():
    """Verify search_web uses SearXNG path when no env var is set."""
    env_copy = os.environ.copy()
    os.environ.pop("WEB_MCP_SEARCH_PROVIDER", None)

    try:
        import importlib

        import web_mcp.tools._core as core_module

        importlib.reload(core_module)
        assert core_module._SEARCH_PROVIDER == "searxng"

        import web_mcp.tools.search as search_module

        importlib.reload(search_module)

        mock_result = "*mocked searxng result*"
        with patch.object(search_module, "_search_brave", new_callable=AsyncMock) as mock_brave:
            with patch.object(
                search_module, "_search_searxng", new_callable=AsyncMock
            ) as mock_searxng:
                mock_searxng.return_value = mock_result

                result = await search_module.search_web(query="test query")

        assert result == mock_result
        mock_brave.assert_not_called()
        mock_searxng.assert_called_once()
        call_args = mock_searxng.call_args
        assert call_args[0][0] == "test query"
    finally:
        os.environ.clear()
        os.environ.update(env_copy)


async def test_search_uses_searxng_when_explicitly_configured():
    """Verify search_web uses SearXNG when WEB_MCP_SEARCH_PROVIDER=searxng."""
    with patch.dict(os.environ, {"WEB_MCP_SEARCH_PROVIDER": "searxng"}):
        import importlib

        import web_mcp.tools._core as core_module

        importlib.reload(core_module)
        assert core_module._SEARCH_PROVIDER == "searxng"

        import web_mcp.tools.search as search_module

        importlib.reload(search_module)

        mock_result = "*mocked searxng result*"
        with patch.object(search_module, "_search_brave", new_callable=AsyncMock) as mock_brave:
            with patch.object(
                search_module, "_search_searxng", new_callable=AsyncMock
            ) as mock_searxng:
                mock_searxng.return_value = mock_result

                result = await search_module.search_web(query="test query", time_range="day")

        assert result == mock_result
        mock_brave.assert_not_called()
        mock_searxng.assert_called_once()


async def test_search_brave_fallback_when_key_missing():
    """Verify _search_brave returns error message when no BRAVE_API_KEY is set."""
    with patch.dict(os.environ, {"WEB_MCP_SEARCH_PROVIDER": "brave"}):
        import importlib

        import web_mcp.tools._core as core_module

        importlib.reload(core_module)

        import web_mcp.tools.search as search_module

        importlib.reload(search_module)

        with patch("web_mcp.brave.search", new_callable=AsyncMock) as mock_brave_search:
            from web_mcp.brave import BraveSearchError

            mock_brave_search.side_effect = BraveSearchError(
                "BRAVE_API_KEY environment variable not set"
            )

            result = await search_module._search_brave("test query")

        assert "Brave Search failed" in result
        assert "BRAVE_API_KEY environment variable not set" in result


async def test_brave_search_tool_always_uses_brave_api():
    """Verify brave_search tool bypasses provider config and always uses Brave API."""
    with patch.dict(os.environ, {"WEB_MCP_SEARCH_PROVIDER": "searxng"}):
        import importlib

        import web_mcp.tools._core as core_module

        importlib.reload(core_module)
        assert core_module._SEARCH_PROVIDER == "searxng"

        import web_mcp.tools.search as search_module

        importlib.reload(search_module)

        mock_results = [
            {
                "title": "Brave Result",
                "url": "https://example.com",
                "snippet": "test content",
            }
        ]

        with patch("web_mcp.brave.search", new_callable=AsyncMock) as mock_brave:
            with patch.object(search_module, "deduplicate_results", return_value=mock_results):
                mock_brave.return_value = mock_results

                result = await search_module.brave_search(query="test query")

        mock_brave.assert_called_once()
        call_kwargs = mock_brave.call_args.kwargs
        assert call_kwargs["max_results"] == 5
        assert "Brave Result" in result


async def test_search_provider_module_variable():
    """Verify _SEARCH_PROVIDER is set correctly from environment."""
    with patch.dict(os.environ, {"WEB_MCP_SEARCH_PROVIDER": "brave"}):
        import importlib

        import web_mcp.tools._core as core_module

        importlib.reload(core_module)
        assert hasattr(core_module, "_SEARCH_PROVIDER")
        assert core_module._SEARCH_PROVIDER == "brave"


async def test_search_provider_default():
    """Verify _SEARCH_PROVIDER defaults to searxng."""
    env_copy = os.environ.copy()
    os.environ.pop("WEB_MCP_SEARCH_PROVIDER", None)

    try:
        import importlib

        import web_mcp.tools._core as core_module

        importlib.reload(core_module)
        assert hasattr(core_module, "_SEARCH_PROVIDER")
        assert core_module._SEARCH_PROVIDER == "searxng"
    finally:
        os.environ.clear()
        os.environ.update(env_copy)


async def test_brave_search_tool_description():
    """Verify brave_search tool description mentions provider config."""
    with patch.dict(os.environ, {"WEB_MCP_SEARCH_PROVIDER": "searxng"}):
        import importlib

        import web_mcp.tools.search as search_module

        importlib.reload(search_module)
        # Check the docstring of brave_search
        assert "WEB_MCP_SEARCH_PROVIDER=brave" in search_module.brave_search.__doc__
