"""SearXNG search module for web browsing MCP server."""

import asyncio
import logging
import os
import re
import time
import time as _time
import urllib.parse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from web_mcp.cache import LRUCache

logger = logging.getLogger(__name__)

_SEARCH_CACHE_TTL = 300
_search_cache: LRUCache | None = None

INSTANCES_URL = "https://searx.space/data/instances.json"
INSTANCES_CACHE_TTL = 3600
BLACKLIST_TTL = 300
MAX_RETRIES = 3

_instances_cache: tuple[float, list[str]] = (0, [])
_blacklist: dict[str, float] = {}


@dataclass
class SearchMetrics:
    total_queries: int = 0
    cache_hits: int = 0
    provider_success: dict = field(default_factory=lambda: defaultdict(int))
    provider_failures: dict = field(default_factory=lambda: defaultdict(int))
    latencies: list = field(default_factory=list)


_search_metrics = SearchMetrics()
_MAX_LATENCY_HISTORY = 100


@dataclass
class InstanceStats:
    url: str
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0


_instance_stats: dict[str, InstanceStats] = {}


def _get_instance_score(instance_url: str) -> float:
    """Calculate a score for instance selection (higher = better)."""
    stats = _instance_stats.get(instance_url)
    if not stats:
        return 1.0

    total = stats.success_count + stats.failure_count
    if total < 3:
        return 1.0

    success_rate = stats.success_count / total
    avg_latency = stats.total_latency_ms / total

    latency_score = max(0.1, 1.0 - (avg_latency - 500) / 4500)

    return success_rate * latency_score


def _record_instance_result(url: str, success: bool, latency_ms: float) -> None:
    if url not in _instance_stats:
        _instance_stats[url] = InstanceStats(url=url)

    stats = _instance_stats[url]
    if success:
        stats.success_count += 1
    else:
        stats.failure_count += 1
    stats.total_latency_ms += latency_ms


def reset_instance_stats() -> None:
    """Reset instance stats (for testing)."""
    _instance_stats.clear()


def _record_search(provider: str, success: bool, latency_ms: float) -> None:
    _search_metrics.total_queries += 1
    if success:
        _search_metrics.provider_success[provider] += 1
    else:
        _search_metrics.provider_failures[provider] += 1
    _search_metrics.latencies.append((provider, latency_ms))
    if len(_search_metrics.latencies) > _MAX_LATENCY_HISTORY:
        _search_metrics.latencies.pop(0)


def get_search_metrics() -> dict:
    """Get search analytics as a serializable dict."""
    total = _search_metrics.total_queries or 1
    return {
        "total_queries": _search_metrics.total_queries,
        "cache_hit_rate": round(_search_metrics.cache_hits / total, 3),
        "provider_success_rates": {
            p: round(_search_metrics.provider_success[p] / total, 3)
            for p in _search_metrics.provider_success
        },
        "provider_failures": dict(_search_metrics.provider_failures),
        "avg_latency_ms": (
            round(
                sum(latency for _, latency in _search_metrics.latencies)
                / len(_search_metrics.latencies),
                1,
            )
            if _search_metrics.latencies
            else None
        ),
    }


def reset_search_metrics() -> None:
    """Reset metrics (for testing)."""
    _search_metrics.total_queries = 0
    _search_metrics.cache_hits = 0
    _search_metrics.provider_success.clear()
    _search_metrics.provider_failures.clear()
    _search_metrics.latencies.clear()


_search_queue: asyncio.Queue | None = None
_search_worker_running: bool = False


def _get_search_cache() -> LRUCache:
    global _search_cache
    if _search_cache is None:
        _search_cache = LRUCache(max_size=50)
    return _search_cache


def reset_search_cache() -> None:
    """Reset the search cache. For testing purposes."""
    global _search_cache
    _search_cache = None


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


async def search(query: str, max_results: int = 10, time_range: str | None = None) -> list[dict]:
    """Search using SearXNG with automatic fallback to public instances and DuckDuckGo.

    Requests are queued and executed sequentially to avoid rate limiting.
    Results are cached for 5 minutes keyed on (query, max_results).

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 10)
        time_range: Time range filter: day, week, month, or year

    Returns:
        List of search result dictionaries with title, url, and snippet

    Raises:
        SearXNGError: If all search attempts fail
    """
    start_time = _time.time()
    cache = _get_search_cache()
    cache_key = f"{query}:{max_results}"

    cached = cache.get(cache_key)
    if cached is not None:
        logger.info(f"[SearXNG] Cache hit for query: {query}")
        return cached

    global _search_queue

    loop = asyncio.get_event_loop()
    result_future = loop.create_future()

    if _search_queue is None:
        _search_queue = asyncio.Queue()

    await _search_queue.put((query, max_results, result_future, time_range))

    if _search_queue.qsize() == 1:
        asyncio.create_task(_process_search_queue())

    result = await result_future
    cache.set(cache_key, result, ttl=_SEARCH_CACHE_TTL)

    elapsed_ms = (_time.time() - start_time) * 1000
    if result:
        _record_search("searxng", True, elapsed_ms)
    else:
        _record_search("searxng", False, elapsed_ms)

    return result


async def _process_search_queue():
    """Process queued search requests sequentially."""
    global _search_queue

    while _search_queue and not _search_queue.empty():
        query, max_results, result_future, time_range = await _search_queue.get()

        try:
            result = await _search_impl(query, max_results, time_range)
            if not result_future.done():
                result_future.set_result(result)
        except Exception as e:
            if not result_future.done():
                result_future.set_exception(e)
        finally:
            _search_queue.task_done()


async def _search_impl(query: str, max_results: int, time_range: str | None = None) -> list[dict]:
    """Internal search implementation."""
    import random

    configured_url = get_searxng_url()

    if configured_url:
        configured_url = configured_url.rstrip("/")
        if not _is_blacklisted(configured_url):
            logger.info(f"[SearXNG] Trying configured instance: {configured_url}")
            start = time.time()
            try:
                result = await _search_instance(
                    configured_url, query, max_results, time_range=time_range
                )
                elapsed_ms = (time.time() - start) * 1000
                _record_instance_result(configured_url, True, elapsed_ms)
                logger.info(
                    f"[SearXNG] Success from configured instance - got {len(result)} results"
                )
                return result
            except SearXNGError as e:
                elapsed_ms = (time.time() - start) * 1000
                _record_instance_result(configured_url, False, elapsed_ms)
                logger.warning(f"[SearXNG] Configured instance failed: {e.message}")
                _blacklist_instance(configured_url)

    fallbacks = await _get_fallback_instances()
    available_fallbacks = [u for u in fallbacks if not _is_blacklisted(u)]

    if available_fallbacks:
        scored = [(u, _get_instance_score(u)) for u in available_fallbacks]
        scored.sort(key=lambda x: x[1], reverse=True)

        top_instances = [u for u, _ in scored[:MAX_RETRIES]]

        if len(scored) > MAX_RETRIES and random.random() < 0.2:
            lower = [u for u, s in scored[MAX_RETRIES:] if s > 0.5]
            if lower:
                top_instances[random.randint(0, len(top_instances) - 1)] = random.choice(lower)

        for _attempt, instance_url in enumerate(top_instances):
            start = time.time()
            try:
                result = await _search_instance(
                    instance_url, query, max_results, time_range=time_range, force_html=True
                )
                elapsed_ms = (time.time() - start) * 1000
                _record_instance_result(instance_url, True, elapsed_ms)
                logger.info(f"[SearXNG] Success from fallback - got {len(result)} results")
                return result
            except SearXNGError as e:
                elapsed_ms = (time.time() - start) * 1000
                _record_instance_result(instance_url, False, elapsed_ms)
                logger.warning(f"[SearXNG] Fallback failed: {e.message}")
                _blacklist_instance(instance_url)

    logger.info("[SearXNG] All SearXNG instances failed, trying DuckDuckGo fallback")
    start = time.time()
    try:
        result = await _search_duckduckgo(query, max_results)
        elapsed_ms = (time.time() - start) * 1000
        _record_instance_result("duckduckgo", True, elapsed_ms)
        return result
    except SearXNGError as e:
        elapsed_ms = (time.time() - start) * 1000
        _record_instance_result("duckduckgo", False, elapsed_ms)
        raise SearXNGError(f"All SearXNG attempts failed and DuckDuckGo failed: {e.message}")


async def _search_instance(
    instance_url: str,
    query: str,
    max_results: int,
    time_range: str | None = None,
    force_html: bool = False,
) -> list[dict]:
    """Execute search against a single SearXNG instance.

    Tries JSON API first, falls back to HTML scraping if unavailable.
    If force_html is True, skips HTTP and uses Playwright directly.
    """
    if force_html:
        return await _search_instance_html(instance_url, query, max_results)

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
            if time_range:
                params["time_range"] = time_range

            response = await client.get(search_url, params=params, timeout=timeout)

            if response.status_code == 429:
                logger.info("[SearXNG] JSON API rate limited (429), trying HTML fallback")
                return await _search_instance_html(
                    instance_url, query, max_results, time_range=time_range
                )

            if response.status_code == 403:
                logger.info("[SearXNG] JSON API blocked (403), trying HTML fallback")
                return await _search_instance_html(
                    instance_url, query, max_results, time_range=time_range
                )

            response.raise_for_status()

            try:
                data = response.json()
                results = data.get("results", [])

                if not results:
                    logger.info("[SearXNG] JSON returned no results, trying HTML fallback")
                    return await _search_instance_html(
                        instance_url, query, max_results, time_range=time_range
                    )

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
                return await _search_instance_html(
                    instance_url, query, max_results, time_range=time_range
                )

    except SearXNGError:
        raise
    except httpx.TimeoutException:
        logger.info("[SearXNG] HTTP timeout, trying HTML fallback")
        return await _search_instance_html(instance_url, query, max_results, time_range=time_range)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (403, 406, 429):
            logger.info(f"[SearXNG] HTTP {e.response.status_code}, trying HTML fallback")
            return await _search_instance_html(
                instance_url, query, max_results, time_range=time_range
            )
        raise SearXNGError(f"HTTP error {e.response.status_code}: {e}")
    except httpx.RequestError:
        logger.info("[SearXNG] HTTP request failed, trying HTML fallback")
        return await _search_instance_html(instance_url, query, max_results, time_range=time_range)
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


async def _search_instance_html(
    instance_url: str, query: str, max_results: int, time_range: str | None = None
) -> list[dict]:
    """Search using HTML scraping when JSON API is not available."""
    try:
        from web_mcp.playwright_fetcher import PlaywrightFetchError, fetch_with_playwright
    except ImportError:
        raise SearXNGError("Playwright not available for HTML fallback")

    encoded_query = urllib.parse.quote(query)
    search_url = f"{instance_url}/search?q={encoded_query}"

    if time_range:
        search_url += f"&time={time_range}"

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

        uddg_match = re.search(
            r'href="[^"]*uddg=([^"&]+)[^"]*"',
            result_html,
            re.IGNORECASE,
        )

        if uddg_match:
            url = urllib.parse.unquote(uddg_match.group(1))
        else:
            url_match = re.search(
                r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>',
                result_html,
                re.IGNORECASE,
            )
            url = url_match.group(1) if url_match else ""
            if url.startswith("//"):
                url = "https:" + url

        if not url:
            continue

        if "y.js?" in url or "ad_domain=" in url or "duckduckgo.com" in url:
            continue

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

        title = remove_html_tags(title_match.group(1)) if title_match else ""
        snippet = remove_html_tags(snippet_match.group(1)) if snippet_match else ""

        if not title:
            continue

        results.append(
            {
                "title": title.strip(),
                "url": url.strip(),
                "snippet": snippet.strip(),
            }
        )

    return results


def deduplicate_results(results: list[dict]) -> list[dict]:
    """Remove duplicate URLs, keeping the highest-scored version."""
    seen: dict[str, int] = {}  # url -> index in result list
    for i, r in enumerate(results):
        url = (r.get("url") or "").rstrip("/")
        if not url:
            continue
        existing = seen.get(url)
        if existing is None:
            seen[url] = i
        else:
            # Keep the one with higher score/bm25_score
            existing_score = results[existing].get("score", 0) or results[existing].get(
                "bm25_score", 0
            )
            new_score = r.get("score", 0) or r.get("bm25_score", 0)
            if new_score > existing_score:
                results[existing] = r
    return [results[i] for i in seen.values()]


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
