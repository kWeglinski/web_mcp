"""SearXNG search module for web browsing MCP server."""

import asyncio
import logging
import os
import re
import time
import urllib.parse
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

INSTANCES_URL = "https://searx.space/data/instances.json"
INSTANCES_CACHE_TTL = 3600
BLACKLIST_TTL = 300
MAX_RETRIES = 20

_instances_cache: tuple[float, list[str]] = (0, [])
_blacklist: dict[str, float] = {}
_search_queue: asyncio.Queue | None = None
_search_worker_running: bool = False


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
    """Search using SearXNG with automatic fallback to public instances and DuckDuckGo.

    Requests are queued and executed sequentially to avoid rate limiting.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of search result dictionaries with title, url, and snippet

    Raises:
        SearXNGError: If all search attempts fail
    """
    global _search_queue

    loop = asyncio.get_event_loop()
    result_future = loop.create_future()

    if _search_queue is None:
        _search_queue = asyncio.Queue()

    await _search_queue.put((query, max_results, result_future))

    if _search_queue.qsize() == 1:
        asyncio.create_task(_process_search_queue())

    return await result_future


async def _process_search_queue():
    """Process queued search requests sequentially."""
    global _search_queue

    while _search_queue and not _search_queue.empty():
        query, max_results, result_future = await _search_queue.get()

        try:
            result = await _search_impl(query, max_results)
            if not result_future.done():
                result_future.set_result(result)
        except Exception as e:
            if not result_future.done():
                result_future.set_exception(e)
        finally:
            _search_queue.task_done()


async def _search_impl(query: str, max_results: int) -> list[dict]:
    """Internal search implementation."""
    configured_url = get_searxng_url()

    instances_to_try = []
    if configured_url:
        instances_to_try.append(configured_url.rstrip("/"))

    fallbacks = await _get_fallback_instances()
    for url in fallbacks:
        if url not in instances_to_try:
            instances_to_try.append(url)

    if not instances_to_try:
        logger.info("[SearXNG] No SearXNG instances available, trying DuckDuckGo fallback")
        try:
            return await _search_duckduckgo(query, max_results)
        except SearXNGError as e:
            raise SearXNGError(f"No instances available and DuckDuckGo failed: {e.message}")

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
            logger.warning(f"[SearXNG] Failed attempt {attempts} on {instance_url}: {e.message}")
            _blacklist_instance(instance_url)
            continue

    logger.info("[SearXNG] All SearXNG instances failed, trying DuckDuckGo fallback")
    try:
        return await _search_duckduckgo(query, max_results)
    except SearXNGError as e:
        raise SearXNGError(f"All SearXNG attempts failed and DuckDuckGo failed: {e.message}")


async def _search_instance(instance_url: str, query: str, max_results: int) -> list[dict]:
    """Execute search against a single SearXNG instance.

    Tries JSON API first, falls back to HTML scraping if unavailable.
    """
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

            if response.status_code == 403:
                logger.info("[SearXNG] JSON API blocked (403), trying HTML fallback")
                return await _search_instance_html(instance_url, query, max_results)

            response.raise_for_status()

            try:
                data = response.json()
                results = data.get("results", [])

                if not results:
                    logger.info("[SearXNG] JSON returned no results, trying HTML fallback")
                    return await _search_instance_html(instance_url, query, max_results)

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

            except (ValueError, KeyError) as e:
                logger.info(f"[SearXNG] JSON parse failed ({e}), trying HTML fallback")
                return await _search_instance_html(instance_url, query, max_results)

    except SearXNGError:
        raise
    except httpx.TimeoutException as e:
        raise SearXNGError(f"Request timed out: {e}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (403, 406):
            logger.info(f"[SearXNG] HTTP {e.response.status_code}, trying HTML fallback")
            return await _search_instance_html(instance_url, query, max_results)
        raise SearXNGError(f"HTTP error {e.response.status_code}: {e}")
    except httpx.RequestError as e:
        raise SearXNGError(f"Request failed: {e}")
    except Exception as e:
        raise SearXNGError(f"Search failed: {e}")


def _parse_searxng_html(html: str, max_results: int) -> list[dict]:
    """Parse SearXNG HTML response to extract search results."""
    results = []

    result_pattern = re.compile(
        r'<article[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</article>',
        re.DOTALL | re.IGNORECASE,
    )

    for match in result_pattern.finditer(html):
        if len(results) >= max_results:
            break

        result_html = match.group(1)

        url_match = re.search(
            r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*url[^"]*"[^>]*>',
            result_html,
            re.IGNORECASE,
        )
        if not url_match:
            url_match = re.search(
                r'<a[^>]*class="[^"]*url[^"]*"[^>]*href="([^"]+)"[^>]*>',
                result_html,
                re.IGNORECASE,
            )
        if not url_match:
            url_match = re.search(
                r'<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>',
                result_html,
                re.DOTALL | re.IGNORECASE,
            )

        title_match = re.search(
            r"<h3[^>]*>.*?<a[^>]*>(.*?)</a>.*?</h3>",
            result_html,
            re.DOTALL | re.IGNORECASE,
        )
        if not title_match:
            title_match = re.search(
                r'<a[^>]*class="[^"]*result-title[^"]*"[^>]*>(.*?)</a>',
                result_html,
                re.DOTALL | re.IGNORECASE,
            )

        content_match = re.search(
            r'<p[^>]*class="[^"]*result-content[^"]*"[^>]*>(.*?)</p>',
            result_html,
            re.DOTALL | re.IGNORECASE,
        )
        if not content_match:
            content_match = re.search(
                r'<span[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</span>',
                result_html,
                re.DOTALL | re.IGNORECASE,
            )

        url = url_match.group(1) if url_match else ""
        title = remove_html_tags(title_match.group(1)) if title_match else ""
        content = remove_html_tags(content_match.group(1)) if content_match else ""

        if not url or not title:
            continue

        results.append(
            {
                "title": title.strip(),
                "url": url.strip(),
                "snippet": content.strip(),
            }
        )

    return results


async def _search_instance_html(instance_url: str, query: str, max_results: int) -> list[dict]:
    """Search using HTML scraping when JSON API is not available."""
    try:
        from web_mcp.playwright_fetcher import PlaywrightFetchError, fetch_with_playwright
    except ImportError:
        raise SearXNGError("Playwright not available for HTML fallback")

    encoded_query = urllib.parse.quote(query)
    search_url = f"{instance_url}/search?q={encoded_query}"

    logger.info(f"[SearXNG] Attempting HTML scrape of {search_url}")

    html = None

    try:
        html = await fetch_with_playwright(
            search_url,
            timeout=45000,
            wait_for_selector="article, .result, #results, [class*='result']",
            wait_time=3000,
        )
    except PlaywrightFetchError as e:
        if "wait_for_selector" in str(e) or "Timeout" in str(e) or "timeout" in str(e).lower():
            logger.info("[SearXNG] Selector timeout, trying without wait")
            try:
                html = await fetch_with_playwright(
                    search_url,
                    timeout=45000,
                    wait_time=5000,
                )
            except PlaywrightFetchError as e2:
                raise SearXNGError(f"HTML scrape failed: {e2.message}")
        else:
            raise SearXNGError(f"HTML scrape failed: {e.message}")
    except Exception as e:
        raise SearXNGError(f"HTML scrape failed: {e}")

    if not html:
        raise SearXNGError("HTML scrape returned no content")

    if "Too Many Requests" in html or "Rate limit" in html or "429" in html:
        raise SearXNGError("Rate limited (HTML)")

    results = _parse_searxng_html(html, max_results)

    if not results:
        results = _parse_generic_search_html(html, max_results)

    if not results:
        raise SearXNGError("No results found in HTML")

    logger.info(f"[SearXNG] HTML scrape successful - got {len(results)} results")
    return results


async def _search_duckduckgo(query: str, max_results: int) -> list[dict]:
    """Fallback search using DuckDuckGo HTML."""
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    logger.info(f"[SearXNG] Falling back to DuckDuckGo: {search_url}")

    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            response = await client.get(
                search_url, headers=headers, timeout=30, follow_redirects=True
            )
            response.raise_for_status()

            html = response.text
            results = _parse_duckduckgo_html(html, max_results)

            if not results:
                results = _parse_generic_search_html(html, max_results)

            if not results:
                raise SearXNGError("No results from DuckDuckGo")

            logger.info(f"[SearXNG] DuckDuckGo successful - got {len(results)} results")
            return results

    except httpx.HTTPStatusError as e:
        raise SearXNGError(f"DuckDuckGo HTTP error: {e.response.status_code}")
    except httpx.RequestError as e:
        raise SearXNGError(f"DuckDuckGo request failed: {e}")
    except Exception as e:
        raise SearXNGError(f"DuckDuckGo failed: {e}")


def _parse_duckduckgo_html(html: str, max_results: int) -> list[dict]:
    """Parse DuckDuckGo HTML response."""
    results = []

    result_pattern = re.compile(
        r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>',
        re.DOTALL | re.IGNORECASE,
    )

    for match in result_pattern.finditer(html):
        if len(results) >= max_results:
            break

        result_html = match.group(1)

        url_match = re.search(
            r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>',
            result_html,
            re.IGNORECASE,
        )
        if not url_match:
            url_match = re.search(
                r'href="[^"]*uddg=([^"&]+)[^"]*"',
                result_html,
                re.IGNORECASE,
            )

        title_match = re.search(
            r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*>(.*?)</a>',
            result_html,
            re.DOTALL | re.IGNORECASE,
        )

        snippet_match = re.search(
            r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
            result_html,
            re.DOTALL | re.IGNORECASE,
        )

        url = url_match.group(1) if url_match else ""
        if url.startswith("//"):
            url = "https:" + url
        if "uddg=" in url:
            uddg_match = re.search(r"uddg=([^&]+)", url)
            if uddg_match:
                url = urllib.parse.unquote(uddg_match.group(1))

        title = remove_html_tags(title_match.group(1)) if title_match else ""
        snippet = remove_html_tags(snippet_match.group(1)) if snippet_match else ""

        if not url or not title:
            continue

        results.append(
            {
                "title": title.strip(),
                "url": url.strip(),
                "snippet": snippet.strip(),
            }
        )

    return results


def _parse_generic_search_html(html: str, max_results: int) -> list[dict]:
    """Fallback parser for various search result HTML structures."""
    results = []

    url_title_pattern = re.compile(
        r'<a[^>]*href="(https?://[^"]+)"[^>]*>([^<]{5,}?)</a>',
        re.IGNORECASE,
    )

    seen_urls = set()
    for match in url_title_pattern.finditer(html):
        if len(results) >= max_results:
            break

        url = match.group(1).strip()
        title = match.group(2).strip()

        if url in seen_urls:
            continue
        if any(skip in url.lower() for skip in ["search?", "page=", "javascript:", "mailto:"]):
            continue
        if len(title) < 3:
            continue

        seen_urls.add(url)
        results.append(
            {
                "title": title,
                "url": url,
                "snippet": "",
            }
        )

    return results
