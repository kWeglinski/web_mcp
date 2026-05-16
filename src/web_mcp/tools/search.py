"""Search tools: search_web, brave_search, search_metrics."""

from web_mcp.logging import get_logger
from web_mcp.searxng import (
    deduplicate_results,
    get_search_metrics,
    parse_searxng_to_markdown,
    search,
)
from web_mcp.tools._core import _SEARCH_PROVIDER

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


async def wikipedia_research(
    query: str, max_sources: int = 5, search_results_limit: int = 10
) -> str:
    """Perform deep research on Wikipedia using a RAG pipeline. Returns an answer with citations."""
    from web_mcp.research.citations import format_sources
    from web_mcp.research.kiwix_pipeline import research_kiwix

    logger.info(f"[wikipedia_research] Starting research: query='{query}', max_sources={max_sources}, search_limit={search_results_limit}")

    try:
        result = await research_kiwix(
            query, max_sources=max_sources, search_results_limit=search_results_limit
        )

        if result.answer.startswith("Error:"):
            logger.warning(f"[wikipedia_research] Returned error: {result.answer}")
            return result.answer

        logger.info(f"[wikipedia_research] Completed in {result.elapsed_ms}ms with {len(result.sources)} sources")

        # Format the output: Answer + Formatted Sources
        output = f"{result.answer}\n\n**Sources:**\n\n{format_sources(result.sources)}"
        return output
    except Exception as e:
        logger.error(f"[wikipedia_research] Failed: {e}", exc_info=True)
        return f"*Wikipedia research failed: {e}*"


async def wikipedia_search(query: str) -> str:
    """Search Kiwix for information. Returns top 5 results in markdown format."""
    from web_mcp.kiwix_client import KiwixClient
    from web_mcp.searxng import parse_searxng_to_markdown

    logger.info(f"[wikipedia_search] Searching Kiwix: query='{query}'")

    try:
        client = KiwixClient()
        logger.debug(f"[wikipedia_search] KiwixClient initialized with URL: {client.kiwix_url}, ZIM: {client.kiwix_wikipedia_zim}")

        results = await client.search(query)
        logger.info(f"[wikipedia_search] Kiwix returned {len(results)} results")

        if not results:
            logger.info("[wikipedia_search] No results found")
            return "*No Kiwix search results found*"

        # Standardize results to match SearXNG format for reuse of parse_searxng_to_markdown
        standardized_results = []
        skipped = 0
        for r in results:
            # Kiwix might return different field names, we try to be robust
            title = r.get("title") or r.get("name") or ""
            url = r.get("url") or r.get("link") or ""
            snippet = r.get("snippet") or r.get("content") or r.get("description") or ""

            if title and url:
                standardized_results.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "score": 1.0,
                    }
                )
            else:
                skipped += 1
                logger.debug(f"[wikipedia_search] Skipped result with missing title/url: {r}")

        if skipped:
            logger.info(f"[wikipedia_search] Skipped {skipped} results with missing title/url")

        if not standardized_results:
            logger.info("[wikipedia_search] No meaningful results after standardization")
            return "*No meaningful Kiwix search results found*"

        logger.info(f"[wikipedia_search] Standardized {len(standardized_results)} results for output")
        json_data = {"results": standardized_results}
        return parse_searxng_to_markdown(json_data, query, max_results=5)

    except ValueError as e:
        logger.error(f"[wikipedia_search] Configuration error: {e}")
        return f"*Wikipedia search failed: Kiwix not configured ({e})*"
    except Exception as e:
        logger.error(f"[wikipedia_search] Failed: {e}", exc_info=True)
        return f"*Wikipedia search failed: {e}*"
