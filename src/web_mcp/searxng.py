"""SearXNG search module for web browsing MCP server."""

import logging
import os
import re
import time
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

INSTANCES_URL = "https://searx.space/data/instances.json"
INSTANCES_CACHE_TTL = 3600
BLACKLIST_TTL = 300
MAX_RETRIES = 20

_instances_cache: tuple[float, list[str]] = (0, [])
_blacklist: dict[str, float] = {}


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


def _is_blacklisted(url: str) -> bool:
    """Check if URL is currently blacklisted."""
    if url in _blacklist:
        if time.time() - _blacklist[url] < BLACKLIST_TTL:
            return True
        del _blacklist[url]
    return False


def _blacklist_instance(url: str) -> None:
    """Add instance to temporary blacklist."""
    _blacklist[url] = time.time()


async def _fetch_public_instances() -> list[str]:
    """Fetch and cache public SearXNG instances from searx.space."""
    global _instances_cache

    if time.time() - _instances_cache[0] < INSTANCES_CACHE_TTL:
        logger.debug(f"[SearXNG] Using cached instances ({len(_instances_cache[1])} available)")
        return _instances_cache[1]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(INSTANCES_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            instances = []
            for url, info in data.get("instances", {}).items():
                if info.get("version") and not info.get("error"):
                    timing = info.get("timing", {}).get("initial", {})
                    if timing and timing.get("success_percentage", 0) >= 80:
                        instances.append(url.rstrip("/"))

            instances.sort(
                key=lambda u: (
                    data.get("instances", {})
                    .get(u + "/" if not u.endswith("/") else u, {})
                    .get("timing", {})
                    .get("initial", {})
                    .get("median", float("inf"))
                )
            )

            _instances_cache = (time.time(), instances[:20])
            logger.info(
                f"[SearXNG] Fetched {len(_instances_cache[1])} public instances from searx.space"
            )
            return _instances_cache[1]

    except Exception as e:
        logger.warning(f"[SearXNG] Failed to fetch public instances: {e}")
        return _instances_cache[1] if _instances_cache[1] else []


async def _get_fallback_instances() -> list[str]:
    """Get available fallback instances, excluding blacklisted ones."""
    instances = await _fetch_public_instances()
    return [u for u in instances if not _is_blacklisted(u)]


def _is_failure_response(data: dict | None, status_code: int) -> bool:
    """Check if response indicates a failure (rate limit, captcha, etc.)."""
    if status_code == 429:
        return True
    if data is None:
        return True
    results = data.get("results", [])
    if not results:
        return True
    return False


async def search(query: str, max_results: int = 10) -> list[dict]:
    """Search using SearXNG with automatic fallback to public instances.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of search result dictionaries with title, url, and snippet

    Raises:
        SearXNGError: If all search attempts fail
    """
    configured_url = get_searxng_url()

    instances_to_try = []
    if configured_url:
        instances_to_try.append(configured_url.rstrip("/"))

    fallbacks = await _get_fallback_instances()
    for url in fallbacks:
        if url not in instances_to_try:
            instances_to_try.append(url)

    if not instances_to_try:
        raise SearXNGError("SearXNG is not configured and no public instances available.")

    last_error: str = ""
    attempts = 0

    for instance_url in instances_to_try[: MAX_RETRIES + 1]:
        if _is_blacklisted(instance_url):
            continue

        attempts += 1
        logger.info(f"[SearXNG] Attempt {attempts}: Trying {instance_url}")
        try:
            result = await _search_instance(instance_url, query, max_results)
            logger.info(
                f"[SearXNG] Success on attempt {attempts} from {instance_url} - got {len(result)} results"
            )
            return result
        except SearXNGError as e:
            last_error = e.message
            logger.warning(f"[SearXNG] Failed attempt {attempts} on {instance_url}: {e.message}")
            _blacklist_instance(instance_url)
            continue

    raise SearXNGError(f"All search attempts failed. Last error: {last_error}")


async def _search_instance(instance_url: str, query: str, max_results: int) -> list[dict]:
    """Execute search against a single SearXNG instance."""
    search_url = f"{instance_url}/search"
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

            if response.status_code == 429:
                raise SearXNGError("Rate limited")

            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if not results:
                raise SearXNGError("No results returned")

            formatted_results = []
            for result in results:
                formatted_result = {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", result.get("snippet", "")),
                }

                if "publishedDate" in result:
                    formatted_result["published_date"] = result["publishedDate"]
                if "score" in result:
                    formatted_result["score"] = result["score"]

                formatted_results.append(formatted_result)

            return formatted_results

    except SearXNGError:
        raise
    except httpx.TimeoutException as e:
        raise SearXNGError(f"Request timed out: {e}")
    except httpx.HTTPStatusError as e:
        raise SearXNGError(f"HTTP error {e.response.status_code}: {e}")
    except httpx.RequestError as e:
        raise SearXNGError(f"Request failed: {e}")
    except Exception as e:
        raise SearXNGError(f"Search failed: {e}")
