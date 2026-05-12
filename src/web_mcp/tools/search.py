"""Search tools: search_web, brave_search, search_metrics."""

from web_mcp.logging import get_logger
from web_mcp.searxng import deduplicate_results, get_search_metrics, parse_searxng_to_markdown, search
from web_mcp.tools._core import _SEARCH_PROVIDER, increment_request_count

logger = get_logger(__name__)


async def _search_web_brave_fallback(query: str) -> list[dict] | None:
    """Attempt Brave search as fallback when SearXNG returns no results."""
    from web_mcp.brave import BraveSearchError, get_brave_api_key

    if not get_brave_api_key():
        return None

    try:
        from web_mcp.brave import search as brave_search_impl

        results = await brave_search_impl(query, max_results=20)
        if results:
            logger.info(f"[search_web] Brave fallback returned {len(results)} results")
            return results
    except (BraveSearchError, Exception) as e:
        logger.warning(f"[search_web] Brave fallback failed: {e}")

    return None


async def _search_brave(query: str) -> str:
    """Primary Brave search implementation."""
    from web_mcp.brave import BraveSearchError, parse_brave_to_markdown
    from web_mcp.brave import search as brave_search_impl

    try:
        results = await brave_search_impl(query, max_results=5)
        if not results:
            return "*No search results found*"

        from web_mcp.research.bm25 import rerank_search_results

        results = rerank_search_results(results, query)
        json_data = {"web": {"results": results}}
        return parse_brave_to_markdown(json_data, query, max_results=5)

    except BraveSearchError as e:
        return f"*Brave Search failed: {e.message}*"


async def _search_searxng(query: str, time_range: str | None = None) -> str:
    """Primary SearXNG search with Brave fallback implementation."""
    from web_mcp.searxng import parse_searxng_to_markdown

    try:
        results = await search(query, 30, time_range=time_range)

        if results:
            results = deduplicate_results(results)

        has_meaningful = any(
            r.get("score", 0) or r.get("bm25_score", 0) or (r.get("content") or r.get("snippet"))
            for r in results
        )
        if not has_meaningful:
            logger.info(
                "[search_web] SearXNG returned no meaningful results, trying Brave fallback"
            )
            brave_results = await _search_web_brave_fallback(query)
            if brave_results:
                results = brave_results

        if results:
            from web_mcp.research.bm25 import rerank_search_results

            results = rerank_search_results(results, query)

        json_data = {"results": results}
        return parse_searxng_to_markdown(json_data, query, max_results=5)

    except Exception as e:
        logger.warning(f"[search_web] SearXNG failed: {e}, trying Brave fallback")
        brave_results = await _search_web_brave_fallback(query)
        if brave_results:
            from web_mcp.research.bm25 import rerank_search_results

            brave_results = rerank_search_results(brave_results, query)
            json_data = {"results": brave_results}
            return parse_searxng_to_markdown(json_data, query, max_results=5)

        return f"*Search failed: {e}*"


async def search_web(
    query: str,
    time_range: str | None = None,
) -> str:
    """Search the web via SearXNG. Returns top 5 results ranked by BM25 relevance."""
    if _SEARCH_PROVIDER == "brave":
        return await _search_brave(query)

    return await _search_searxng(query, time_range=time_range)


async def search_metrics() -> dict:
    """Get search analytics: provider success rates, cache hit rate, avg latency."""
    return get_search_metrics()


async def brave_search(
    query: str,
    time_range: str | None = None,
) -> str:
    """Search the web via Brave Search API (primary). Use WEB_MCP_SEARCH_PROVIDER=brave to make it default."""
    from web_mcp.brave import BraveSearchError, parse_brave_to_markdown
    from web_mcp.brave import search as brave_search_impl

    try:
        results = await brave_search_impl(query, max_results=5, time_range=time_range)

        if results:
            results = deduplicate_results(results)

        json_data = {
            "web": {
                "results": [
                    {
                        "title": r["title"],
                        "url": r["url"],
                        "description": r["snippet"],
                        "page_age": r.get("published_date", ""),
                        "profile": {"name": ""},
                    }
                    for r in results
                ]
            }
        }
        return parse_brave_to_markdown(json_data, query, max_results=5)

    except BraveSearchError as e:
        return f"*Brave Search failed: {e.message}*"
    except Exception as e:
        return f"*Brave Search failed: {e}*"
