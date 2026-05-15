"""Unit tests for search tools (search_web, brave_search, search_metrics, wikipedia)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSearchWeb:
    @pytest.mark.asyncio
    async def test_search_web_searxng_default(self):
        from web_mcp.tools.search import search_web

        with (
            patch("web_mcp.tools.search._SEARCH_PROVIDER", "searxng"),
            patch("web_mcp.tools.search._search_searxng") as mock_searxng,
        ):
            mock_searxng.return_value = "# Search results\n\n[Link](https://example.com)"
            result = await search_web("test query")
            assert "Search results" in result
            mock_searxng.assert_called_once_with("test query", time_range=None)

    @pytest.mark.asyncio
    async def test_search_web_searxng_with_time_range(self):
        from web_mcp.tools.search import search_web

        with (
            patch("web_mcp.tools.search._SEARCH_PROVIDER", "searxng"),
            patch("web_mcp.tools.search._search_searxng") as mock_searxng,
        ):
            mock_searxng.return_value = "# Results"
            await search_web("test query", time_range="month")
            mock_searxng.assert_called_once_with("test query", time_range="month")

    @pytest.mark.asyncio
    async def test_search_web_brave_fallback(self):
        from web_mcp.tools.search import search_web

        with (
            patch("web_mcp.tools.search._SEARCH_PROVIDER", "searxng"),
            patch("web_mcp.tools.search._search_searxng") as mock_searxng,
        ):
            mock_searxng.return_value = "# Results with Brave fallback"
            result = await search_web("test query")
            assert "Brave" in result

    @pytest.mark.asyncio
    async def test_search_web_no_results(self):
        from web_mcp.tools.search import search_web

        with (
            patch("web_mcp.tools.search._SEARCH_PROVIDER", "searxng"),
            patch("web_mcp.tools.search._search_searxng") as mock_searxng,
        ):
            mock_searxng.return_value = "# No results"
            result = await search_web("test query")
            assert "No results" in result


class TestSearchBraveFallback:
    @pytest.mark.asyncio
    async def test_brave_fallback_no_api_key(self):
        from web_mcp.tools.search import _search_web_brave_fallback

        with patch("web_mcp.brave.get_brave_api_key") as mock_key:
            mock_key.return_value = None
            result = await _search_web_brave_fallback("test query")
            assert result is None

    @pytest.mark.asyncio
    async def test_brave_fallback_no_results(self):
        from web_mcp.tools.search import _search_web_brave_fallback

        with (
            patch("web_mcp.brave.get_brave_api_key") as mock_key,
            patch("web_mcp.brave.search", new_callable=AsyncMock) as mock_search,
        ):
            mock_key.return_value = "fake_key"
            mock_search.return_value = []
            result = await _search_web_brave_fallback("test query")
            assert result is None

    @pytest.mark.asyncio
    async def test_brave_fallback_with_results(self):
        from web_mcp.tools.search import _search_web_brave_fallback

        with (
            patch("web_mcp.brave.get_brave_api_key") as mock_key,
            patch("web_mcp.brave.search", new_callable=AsyncMock) as mock_search,
        ):
            mock_key.return_value = "fake_key"
            mock_search.return_value = [{"title": "Result 1", "url": "https://example.com"}]
            result = await _search_web_brave_fallback("test query")
            assert result is not None
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_brave_fallback_error(self):
        from web_mcp.brave import BraveSearchError
        from web_mcp.tools.search import _search_web_brave_fallback

        with (
            patch("web_mcp.brave.get_brave_api_key") as mock_key,
            patch("web_mcp.brave.search") as mock_search,
        ):
            mock_key.return_value = "fake_key"
            mock_search.side_effect = BraveSearchError("API error")
            result = await _search_web_brave_fallback("test query")
            assert result is None


class TestSearchBrave:
    @pytest.mark.asyncio
    async def test_search_brave_success(self):
        from web_mcp.tools.search import _search_brave

        with (
            patch("web_mcp.brave.search") as mock_search,
            patch("web_mcp.brave.parse_brave_to_markdown") as mock_parse,
        ):
            mock_search.return_value = AsyncMock(
                return_value=[
                    {
                        "title": "Result 1",
                        "url": "https://example.com",
                        "snippet": "Description",
                        "published_date": "2024-01-01",
                    }
                ]
            )
            mock_parse.return_value = "*Brave results*"
            result = await _search_brave("test query")
            assert "Brave results" in result

    @pytest.mark.asyncio
    async def test_search_brave_no_results(self):
        from web_mcp.tools.search import _search_brave

        with patch("web_mcp.brave.search") as mock_search:
            mock_search.return_value = AsyncMock(return_value=[])
            result = await _search_brave("test query")
            assert "No search results found" in result

    @pytest.mark.asyncio
    async def test_search_brave_error(self):
        from web_mcp.brave import BraveSearchError
        from web_mcp.tools.search import _search_brave

        with patch("web_mcp.brave.search") as mock_search:
            mock_search.side_effect = BraveSearchError("API key invalid")
            result = await _search_brave("test query")
            assert "Brave Search failed" in result


class TestSearchSearxng:
    @pytest.mark.asyncio
    async def test_search_searxng_success(self):
        from web_mcp.tools.search import _search_searxng

        with (
            patch("web_mcp.tools.search.search") as mock_search,
            patch("web_mcp.searxng.deduplicate_results") as mock_dedup,
            patch("web_mcp.tools.search.parse_searxng_to_markdown") as mock_parse,
        ):
            mock_search.return_value = [
                {
                    "title": "Result 1",
                    "url": "https://example.com",
                    "snippet": "Description",
                    "score": 0.95,
                }
            ]
            mock_dedup.return_value = mock_search.return_value
            mock_parse.return_value = "# Results"
            result = await _search_searxng("test query")
            assert "Results" in result

    @pytest.mark.asyncio
    async def test_search_searxng_no_meaningful_triggers_brave(self):
        from web_mcp.tools.search import _search_searxng

        with (
            patch("web_mcp.tools.search.search") as mock_search,
            patch("web_mcp.searxng.deduplicate_results") as mock_dedup,
            patch("web_mcp.tools.search._search_web_brave_fallback") as mock_brave,
            patch("web_mcp.tools.search.parse_searxng_to_markdown") as mock_parse,
        ):
            mock_search.return_value = [
                {"title": "Result", "url": "https://example.com", "score": 0, "content": None}
            ]
            mock_dedup.return_value = mock_search.return_value
            mock_brave.return_value = [{"title": "Brave result", "url": "https://brave.com"}]
            mock_parse.return_value = "*Brave fallback*"
            result = await _search_searxng("test query")
            assert "Brave fallback" in result

    @pytest.mark.asyncio
    async def test_search_searxng_error_triggers_brave(self):
        from web_mcp.tools.search import _search_searxng

        with (
            patch("web_mcp.tools.search.search") as mock_search,
            patch("web_mcp.tools.search._search_web_brave_fallback") as mock_brave,
            patch("web_mcp.tools.search.parse_searxng_to_markdown") as mock_parse,
        ):
            mock_search.side_effect = Exception("SearXNG down")
            mock_brave.return_value = [{"title": "Brave result", "url": "https://brave.com"}]
            mock_parse.return_value = "*Brave fallback*"
            result = await _search_searxng("test query")
            assert "Brave fallback" in result

    @pytest.mark.asyncio
    async def test_search_searxng_error_no_brave(self):
        from web_mcp.tools.search import _search_searxng

        with (
            patch("web_mcp.tools.search.search") as mock_search,
            patch("web_mcp.tools.search._search_web_brave_fallback") as mock_brave,
        ):
            mock_search.side_effect = Exception("SearXNG down")
            mock_brave.return_value = None
            result = await _search_searxng("test query")
            assert "Search failed" in result


class TestSearchMetrics:
    @pytest.mark.asyncio
    async def test_search_metrics(self):
        from web_mcp.tools.search import search_metrics

        with patch("web_mcp.tools.search.get_search_metrics") as mock_metrics:
            mock_metrics.return_value = {
                "provider": "searxng",
                "success_rate": 0.95,
                "cache_hit_rate": 0.3,
                "avg_latency_ms": 150,
            }
            result = await search_metrics()
            assert result["provider"] == "searxng"
            assert result["success_rate"] == 0.95


class TestBraveSearch:
    @pytest.mark.asyncio
    async def test_brave_search_success(self):
        from web_mcp.tools.search import brave_search

        with (
            patch("web_mcp.brave.search") as mock_search,
            patch("web_mcp.searxng.deduplicate_results") as mock_dedup,
            patch("web_mcp.brave.parse_brave_to_markdown") as mock_parse,
        ):
            mock_search.return_value = AsyncMock(
                return_value=[
                    {
                        "title": "Result 1",
                        "url": "https://example.com",
                        "snippet": "Description",
                        "published_date": "2024-01-01",
                    }
                ]
            )
            mock_dedup.return_value = mock_search.return_value
            mock_parse.return_value = "*Brave search results*"
            result = await brave_search("test query")
            assert "Brave search results" in result

    @pytest.mark.asyncio
    async def test_brave_search_error(self):
        from web_mcp.brave import BraveSearchError
        from web_mcp.tools.search import brave_search

        with patch("web_mcp.brave.search") as mock_search:
            mock_search.side_effect = BraveSearchError("Invalid API key")
            result = await brave_search("test query")
            assert "Brave Search failed" in result

    @pytest.mark.asyncio
    async def test_brave_search_generic_error(self):
        from web_mcp.tools.search import brave_search

        with patch("web_mcp.brave.search") as mock_search:
            mock_search.side_effect = Exception("Unexpected error")
            result = await brave_search("test query")
            assert "Brave Search failed" in result

    @pytest.mark.asyncio
    async def test_brave_search_with_time_range(self):
        from web_mcp.tools.search import brave_search

        with (
            patch("web_mcp.brave.search") as mock_search,
            patch("web_mcp.searxng.deduplicate_results") as mock_dedup,
            patch("web_mcp.brave.parse_brave_to_markdown") as mock_parse,
        ):
            mock_search.return_value = AsyncMock(
                return_value=[{"title": "R", "url": "https://x.com", "snippet": "S"}]
            )
            mock_dedup.return_value = mock_search.return_value
            mock_parse.return_value = "*Results*"
            await brave_search("query", time_range="year")
            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["time_range"] == "year"


class TestWikipediaResearch:
    @pytest.mark.asyncio
    async def test_wikipedia_research_success(self):
        from web_mcp.tools.search import wikipedia_research

        with (
            patch("web_mcp.research.kiwix_pipeline.research_kiwix") as mock_research,
            patch("web_mcp.research.citations.format_sources") as mock_format,
        ):
            mock_result = MagicMock()
            mock_result.answer = "This is the answer"
            mock_result.sources = [{"title": "Source 1", "url": "https://example.com"}]
            mock_research.return_value = mock_result
            mock_format.return_value = "- [Source 1](https://example.com)"

            result = await wikipedia_research("test query")
            assert "This is the answer" in result
            assert "Sources:" in result

    @pytest.mark.asyncio
    async def test_wikipedia_research_error(self):
        from web_mcp.tools.search import wikipedia_research

        with patch("web_mcp.research.kiwix_pipeline.research_kiwix") as mock_research:
            mock_result = MagicMock()
            mock_result.answer = "Error: Kiwix not configured"
            mock_result.sources = []
            mock_research.return_value = mock_result

            result = await wikipedia_research("test query")
            assert "Error: Kiwix not configured" in result

    @pytest.mark.asyncio
    async def test_wikipedia_research_exception(self):
        from web_mcp.tools.search import wikipedia_research

        with patch("web_mcp.research.kiwix_pipeline.research_kiwix") as mock_research:
            mock_research.side_effect = Exception("Unexpected error")

            result = await wikipedia_research("test query")
            assert "Wikipedia research failed" in result


class TestWikipediaSearch:
    @pytest.mark.asyncio
    async def test_wikipedia_search_success(self):
        from web_mcp.tools.search import wikipedia_search

        with patch("web_mcp.kiwix_client.KiwixClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(
                return_value=[
                    {
                        "title": "Wikipedia Article",
                        "url": "https://kiwix.org/article",
                        "snippet": "Snippet text",
                    }
                ]
            )
            mock_client_class.return_value = mock_client

            result = await wikipedia_search("test query")
            assert "Wikipedia Article" in result

    @pytest.mark.asyncio
    async def test_wikipedia_search_no_results(self):
        from web_mcp.tools.search import wikipedia_search

        with patch("web_mcp.kiwix_client.KiwixClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(return_value=[])
            mock_client_class.return_value = mock_client

            result = await wikipedia_search("test query")
            assert "No Kiwix search results found" in result

    @pytest.mark.asyncio
    async def test_wikipedia_search_no_meaningful_results(self):
        from web_mcp.tools.search import wikipedia_search

        with patch("web_mcp.kiwix_client.KiwixClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(return_value=[{"title": "", "url": ""}])
            mock_client_class.return_value = mock_client

            result = await wikipedia_search("test query")
            assert "No meaningful Kiwix search results found" in result

    @pytest.mark.asyncio
    async def test_wikipedia_search_robust_field_names(self):
        from web_mcp.tools.search import wikipedia_search

        with patch("web_mcp.kiwix_client.KiwixClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.search = AsyncMock(
                return_value=[
                    {"name": "Article", "link": "https://kiwix.org/article", "content": "Snippet"}
                ]
            )
            mock_client_class.return_value = mock_client

            result = await wikipedia_search("test query")
            assert "Article" in result
