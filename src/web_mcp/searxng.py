"""SearXNG search module for web browsing MCP server."""

import os
import re
from datetime import datetime

import httpx


def remove_html_tags(text: str | None) -> str:
    """Strip HTML tags and normalize whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^<]+?>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_date(iso_string: str | None) -> str:
    """Convert ISO date to YYYY-MM-DD format."""
    if not iso_string:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return "Unknown"


def parse_searxng_to_markdown(
    json_data: dict,
    query: str = "",
    max_results: int = 10,
    max_content_length: int = 1500,
) -> str:
    """Convert SearXNG JSON to LLM-optimized markdown format.

    Args:
        json_data: SearXNG JSON response containing 'results' array
        query: The original search query for the header
        max_results: Maximum number of results to include (default: 10)
        max_content_length: Maximum content length per result (default: 1500)

    Returns:
        Formatted markdown string optimized for LLM context windows
    """
    raw_results = json_data.get("results", [])

    if not raw_results:
        return "*No search results found*"

    max_score = max([r.get("score", 0) or r.get("bm25_score", 0) for r in raw_results] or [1])
    normalized_results = []

    for result in raw_results:
        score = result.get("score")
        if score is None:
            bm25 = result.get("bm25_score", 0) or 0
            score = bm25 / max_score if max_score else 0

        content = result.get("content", "") or result.get("snippet", "")
        clean_content = remove_html_tags(content)
        if len(clean_content) > max_content_length:
            clean_content = clean_content[:max_content_length] + "..."

        pub_date = result.get("published_date") or result.get("publishedDate")
        formatted_date = parse_date(pub_date)

        normalized_results.append(
            {
                "url": result.get("url", ""),
                "title": result.get("title", ""),
                "content": clean_content,
                "score": score,
                "date": formatted_date,
                "engine": result.get("engine", "unknown"),
                "category": result.get("category", "general"),
            }
        )

    normalized_results.sort(key=lambda x: x["score"], reverse=True)

    output = (
        f'# Search Results for: "{query}"\n**Total Results:** {len(normalized_results)}\n\n---\n\n'
    )

    for i, result in enumerate(normalized_results[:max_results], 1):
        output += f"### Result #{i} (Score: {result['score']:.2f})\n"
        output += f"**Source:** [{result['title']}]({result['url']})  \n"
        output += f"**Published:** {result['date']}  \n"
        output += f"**Engine:** {result['engine'].capitalize()}  \n\n"
        output += "#### Key Findings\n"
        output += f"{result['content']}\n\n"
        output += f"[End of Result #{i}]\n\n---\n\n"

    return output


class SearXNGError(Exception):
    """Custom exception for SearXNG search errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def get_searxng_url() -> str | None:
    """Get the SearXNG URL from environment variable.

    Returns:
        The SearXNG URL if configured, None otherwise.
    """
    return os.environ.get("WEB_MCP_SEARXNG_URL", None)


async def search(query: str, max_results: int = 10) -> list[dict]:
    """Search using SearXNG.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of search result dictionaries with title, url, and snippet

    Raises:
        SearXNGError: If the search fails or SearXNG is not configured
    """
    searxng_url = get_searxng_url()

    if not searxng_url:
        raise SearXNGError(
            "SearXNG is not configured. Set WEB_MCP_SEARXNG_URL environment variable."
        )

    # Clean up the URL - ensure it doesn't have a trailing slash
    searxng_url = searxng_url.rstrip("/")

    # Build the search URL
    # SearXNG API endpoint is typically /search
    search_url = f"{searxng_url}/search"

    timeout = 30

    try:
        async with httpx.AsyncClient() as client:
            params = {
                "q": query,
                "format": "json",
                "pageno": 1,
                "num_results": max_results,
            }
            response = await client.get(search_url, params=params, timeout=timeout)
            response.raise_for_status()

            data = response.json()

            # SearXNG returns results in the 'results' key
            results = data.get("results", [])

            # Parse and format results
            formatted_results = []
            for result in results:
                formatted_result = {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", result.get("snippet", "")),
                }

                # Add optional fields if available
                if "publishedDate" in result:
                    formatted_result["published_date"] = result["publishedDate"]
                if "score" in result:
                    formatted_result["score"] = result["score"]

                formatted_results.append(formatted_result)

            return formatted_results

    except httpx.TimeoutException as e:
        raise SearXNGError(f"Request timed out: {e}")
    except httpx.HTTPStatusError as e:
        raise SearXNGError(f"HTTP error {e.response.status_code}: {e}")
    except httpx.RequestError as e:
        raise SearXNGError(f"Request failed: {e}")
    except Exception as e:
        raise SearXNGError(f"Search failed: {e}")
