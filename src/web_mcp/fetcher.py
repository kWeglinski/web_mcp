"""URL fetching module for web browsing."""

import asyncio
import random
import re
from dataclasses import dataclass
from typing import Any

from web_mcp.cache import get_cache
from web_mcp.config import Config
from web_mcp.logging_utils import get_logger
from web_mcp.security import (
    validate_url,
    validate_url_ip,
    validate_url_no_credentials,
)
from web_mcp.tls_fetcher import TlsFetchError, fetch_with_tls_raw
from web_mcp.utils.retry import with_retry

logger = get_logger(__name__)


class FetchError(Exception):
    """Custom exception for fetch errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ContentLengthExceededError(FetchError):
    """Exception raised when content length exceeds the limit."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RetryableFetchError(FetchError):
    """Exception that indicates the fetch operation can be retried.

    This is raised for transient errors like connection failures, timeouts,
    server errors (5xx), rate limits (429), and anti-bot blocks (403).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _should_retry_response(status_code: int | None) -> bool:
    """Check if a response status code should trigger retry/fallback.

    Args:
        status_code: The HTTP status code to check, or None if unknown

    Returns:
        True if the response should be retried or fallen back to Playwright, False otherwise
    """
    if status_code is None:
        return False
    if 500 <= status_code < 600:
        return True
    if status_code == 429:
        return True
    # 403 indicates anti-bot detection - retry once then fall back to Playwright
    if status_code == 403:
        return True
    return False


async def _apply_request_delay(config: Config) -> None:
    """Apply a random delay before making a request to avoid detection patterns.

    Uses uniform distribution between min and max delay values from config.
    """
    delay = random.uniform(config.request_delay_min, config.request_delay_max)
    await asyncio.sleep(delay)


async def _fetch_with_size_limit(
    url: str,
    config: Config,
    max_content_length: int,
) -> str:
    """Fetch URL with content length limiting using tls-client.

    Args:
        url: The URL to fetch
        config: Configuration object
        max_content_length: Maximum content length in bytes

    Returns:
        Response text content

    Raises:
        ContentLengthExceededError: If content exceeds the limit
        FetchError: For other fetch errors
    """
    try:
        headers = config.http_headers_with_referer(url)

        response_data = await fetch_with_tls_raw(
            url=url,
            headers=headers,
            client_identifier=config.tls_client_identifier,
            timeout_seconds=int(config.request_timeout),
            proxy=config.proxy_url,
        )

        content = response_data["content"]
        if len(content.encode("utf-8", errors="replace")) > max_content_length:
            raise ContentLengthExceededError(
                f"Response size ({len(content)} chars) exceeds maximum allowed "
                f"({max_content_length} bytes)"
            )

        return content

    except ContentLengthExceededError:
        raise
    except TlsFetchError as e:
        status_code = _extract_status_code(str(e))
        if status_code and _should_retry_response(status_code):
            raise RetryableFetchError(str(e))
        logger.error(f"TLS fetch error for URL {url}: {e}")
        raise FetchError(str(e))


def _extract_status_code(error_str: str) -> int | None:
    """Extract HTTP status code from a TlsFetchError message.

    Args:
        error_str: The error message string

    Returns:
        Status code as int, or None if not found
    """
    match = re.search(r"HTTP (\d{3})", error_str)
    if match:
        return int(match.group(1))
    return None


async def _fetch_core(
    url: str,
    config: Config,
    timeout: float | None = None,
    *,
    return_bytes: bool = False,
) -> "_FetchResult":
    """Core fetch logic shared between text and bytes fetchers.

    Performs security validation, applies request delay/jitter, makes HTTP
    request using tls-client with Chrome TLS fingerprint, and content-length checking.

    Args:
        url: The URL to fetch
        config: Configuration object
        timeout: Optional override for request timeout (seconds)
        return_bytes: If True, return bytes; if False, return text

    Returns:
        _FetchResult with content, content-type, final URL, and status code

    Raises:
        FetchError: If the URL cannot be fetched or fails security checks
        ContentLengthExceededError: If content exceeds the limit
        RetryableFetchError: For transient errors that can be retried
    """
    request_timeout = timeout if timeout is not None else float(config.request_timeout)

    if not validate_url(url):
        raise FetchError(f"Invalid URL format: {url}")

    if not validate_url_no_credentials(url):
        raise FetchError("URL with credentials not allowed - potential injection attack")

    if not validate_url_ip(url):
        raise FetchError("URL resolves to private IP address - SSRF attempt blocked")

    # Apply request delay/jitter before every request
    await _apply_request_delay(config)

    try:
        headers = config.http_headers_with_referer(url)

        response_data: dict[str, Any] = await fetch_with_tls_raw(
            url=url,
            headers=headers,
            client_identifier=config.tls_client_identifier,
            timeout_seconds=int(request_timeout),
            proxy=config.proxy_url,
        )

        content_raw: str = response_data["content"]
        status_code: int = response_data.get("status_code", 200)

        # Check if we should retry based on status code
        if _should_retry_response(status_code):
            raise RetryableFetchError(f"HTTP {status_code}: {content_raw[:200]}")

        # Handle content length for text
        if not return_bytes:
            total_chars = 0
            # Simulate streaming by checking chunks
            text_chunks: list[str] = [content_raw]
            for chunk in text_chunks:
                total_chars += len(chunk)
                if total_chars > config.max_content_length:
                    raise ContentLengthExceededError(
                        f"Response size ({total_chars} chars) exceeds maximum allowed "
                        f"({config.max_content_length} bytes)"
                    )

            return _FetchResult(
                content="".join(text_chunks),
                content_type=response_data.get("headers", {}).get(
                    "Content-Type", "text/html; charset=utf-8"
                ),
                final_url=url,
                status_code=status_code,
            )
        else:
            # Handle content length for bytes
            content_bytes = content_raw.encode("utf-8", errors="replace")
            if len(content_bytes) > config.max_content_length:
                raise ContentLengthExceededError(
                    f"Response size ({len(content_bytes)} bytes) exceeds maximum allowed "
                    f"({config.max_content_length} bytes)"
                )

            return _FetchResult(
                content=content_bytes,
                content_type=response_data.get("headers", {}).get(
                    "Content-Type", "application/octet-stream"
                ),
                final_url=url,
                status_code=status_code,
            )

    except RetryableFetchError:
        raise
    except ContentLengthExceededError:
        raise
    except TlsFetchError as e:
        error_str = str(e)
        status_code = _extract_status_code(error_str)

        if status_code and _should_retry_response(status_code):
            raise RetryableFetchError(f"HTTP {status_code}: {e}")

        # Network errors (no HTTP status code) are retryable
        if "network" in error_str.lower() or "connection" in error_str.lower():
            raise RetryableFetchError(str(e))

        logger.error(f"TLS fetch error for URL {url}: {e}")
        raise FetchError(str(e))


@dataclass
class _FetchResult:
    """Internal result of a fetch operation."""

    content: str | bytes
    content_type: str
    final_url: str
    status_code: int


class RedirectValidator:
    """Validates redirect targets before following.

    Ensures that each redirect target passes SSRF protection and
    whitelist/blacklist checks before being followed.

    Note: tls-client follows redirects automatically, so this validator
    is kept for future use with custom redirect handling.
    """

    def __init__(self, max_redirects: int = 5):
        """Initialize the redirect validator.

        Args:
            max_redirects: Maximum number of redirects to follow
        """
        self.max_redirects = max_redirects
        self._redirect_count = 0

    async def should_follow_redirect(self, url: str) -> bool:
        """Check if a redirect target is safe to follow.

        Args:
            url: The redirect target URL

        Returns:
            True if the redirect is safe to follow, False otherwise
        """
        from web_mcp.security import validate_url_with_whitelist

        self._redirect_count += 1

        if self._redirect_count > self.max_redirects:
            logger.warning(f"Redirect limit exceeded: {self._redirect_count}")
            return False

        if not validate_url(url):
            logger.warning(f"Invalid redirect URL format: {url}")
            return False

        if not validate_url_no_credentials(url):
            logger.warning(f"Redirect with credentials blocked: {url}")
            return False

        if not validate_url_ip(url):
            logger.warning(f"Redirect to private IP blocked: {url}")
            return False

        if not validate_url_with_whitelist(url):
            logger.warning(f"Redirect to non-whitelisted domain blocked: {url}")
            return False

        return True

    def reset(self) -> None:
        """Reset redirect counter."""
        self._redirect_count = 0


def get_connection_pool():
    """Get the global connection pool.

    Deprecated: tls-client is now used as the primary fetcher.
    This function exists for backward compatibility with tests.

    Returns:
        None (no longer used)
    """
    return None


async def _fetch_with_redirect_validation(
    url: str, config: Config, timeout: float | None = None
) -> str:
    """Internal fetch function with redirect validation for retry decorator.

    This is the actual fetch operation that will be retried. It performs
    security validation and handles redirects.

    Args:
        url: The URL to fetch
        config: Configuration object with request_timeout
        timeout: Optional override for request timeout

    Returns:
        Raw HTML content

    Raises:
        FetchError: If the URL cannot be fetched or fails security checks
        ContentLengthExceededError: If content exceeds the limit
    """
    result = await _fetch_core(url, config, timeout, return_bytes=False)
    assert isinstance(result.content, str)
    return result.content


@with_retry(
    max_attempts=3,
    base_delay=1.0,
    retryable_exceptions=(TlsFetchError, RetryableFetchError),
    jitter=True,
)
async def fetch_url(url: str, config: Config, timeout: float | None = None) -> str:
    """Fetch HTML content from a URL with security validation.

    This function performs comprehensive security checks before fetching:
    - URL format validation
    - Credential injection prevention
    - SSRF protection via DNS resolution and IP validation
    - Request delay/jitter to avoid detection patterns

    Uses tls-client with a Chrome 120 TLS fingerprint (JA3/JA4) to bypass
    anti-bot detection systems. On 403 errors, the retry decorator will attempt
    up to 3 times before raising.

    Args:
        url: The URL to fetch
        config: Configuration object with request_timeout
        timeout: Optional override for request timeout

    Returns:
        Raw HTML content

    Raises:
        FetchError: If the URL cannot be fetched or fails security checks
        ContentLengthExceededError: If content exceeds the limit
    """
    return await _fetch_with_redirect_validation(url, config, timeout)


async def fetch_url_cached(url: str, config: Config, timeout: float | None = None) -> str:
    """Fetch HTML content from a URL with caching.

    Uses LRU cache to store previously fetched URLs with TTL support.

    Args:
        url: The URL to fetch
        config: Configuration object with request_timeout and cache_ttl
        timeout: Optional override for request timeout

    Returns:
        Raw HTML content

    Raises:
        FetchError: If the URL cannot be fetched
        ContentLengthExceededError: If content exceeds the limit
    """
    cache = get_cache()

    cached = cache.get(url)
    if cached is not None:
        logger.info(f"Cache hit for URL: {url}")
        return cached

    result = await fetch_url(url, config, timeout)

    cache.set(url, result, ttl=config.cache_ttl)

    return result


async def fetch_url_with_fallback(url: str, config: Config, timeout: float | None = None) -> str:
    """Fetch URL with tls-client, fallback to Playwright for JS-heavy pages.

    First attempts to fetch with tls-client (Chrome TLS fingerprint). If the
    response indicates anti-bot detection (403) or content is below the
    configured threshold (indicating possible JS-rendered content),
    falls back to Playwright for full browser rendering.

    Args:
        url: The URL to fetch
        config: Configuration object
        timeout: Optional override for request timeout

    Returns:
        HTML content (either from tls-client or Playwright)

    Raises:
        FetchError: If both tls-client and Playwright fail
        ContentLengthExceededError: If content exceeds the limit
    """
    from web_mcp.playwright_fetcher import (
        PlaywrightFetchError,
        fetch_with_playwright_cached,
    )

    try:
        html = await fetch_url(url, config, timeout)

        if len(html.strip()) < config.playwright_fallback_threshold:
            if config.playwright_enabled:
                logger.info(
                    f"Content too short ({len(html)} chars), falling back to Playwright for: {url}"
                )
                try:
                    return await fetch_with_playwright_cached(url, config)
                except PlaywrightFetchError as e:
                    logger.warning(f"Playwright fallback failed: {e}")
                    return html
        return html

    except FetchError as e:
        if config.playwright_enabled:
            logger.info(f"tls-client fetch failed, trying Playwright: {e}")
            try:
                return await fetch_with_playwright_cached(url, config)
            except PlaywrightFetchError as pe:
                logger.error(f"Playwright also failed: {pe}")
                raise e
        raise


async def close_pool() -> None:
    """Close the connection pool. No-op since tls-client doesn't use a persistent pool."""
    pass


@dataclass
class FetchedContent:
    """Result of fetching a URL with metadata."""

    content: bytes
    content_type: str
    url: str


async def _fetch_url_with_metadata_internal(
    url: str, config: Config, timeout: float | None = None
) -> FetchedContent:
    """Internal fetch function for bytes content with metadata.

    Args:
        url: The URL to fetch
        config: Configuration object with request_timeout
        timeout: Optional override for request timeout

    Returns:
        FetchedContent with bytes content and content-type

    Raises:
        FetchError: If the URL cannot be fetched or fails security checks
        ContentLengthExceededError: If content exceeds the limit
    """
    result = await _fetch_core(url, config, timeout, return_bytes=True)
    assert isinstance(result.content, bytes)
    return FetchedContent(
        content=result.content,
        content_type=result.content_type,
        url=result.final_url,
    )


@with_retry(
    max_attempts=3,
    base_delay=1.0,
    retryable_exceptions=(TlsFetchError, RetryableFetchError),
    jitter=True,
)
async def fetch_url_with_metadata(
    url: str, config: Config, timeout: float | None = None
) -> FetchedContent:
    """Fetch URL content with content-type metadata.

    Returns both the raw content (as bytes) and the content-type header.
    This is useful for handling non-HTML content like PDFs.

    Uses tls-client with a Chrome 120 TLS fingerprint (JA3/JA4) to bypass
    anti-bot detection systems.

    Args:
        url: The URL to fetch
        config: Configuration object
        timeout: Optional override for request timeout

    Returns:
        FetchedContent with bytes content and content-type

    Raises:
        FetchError: If the URL cannot be fetched or fails security checks
        ContentLengthExceededError: If content exceeds the limit
        RetryableFetchError: For transient errors (retried automatically)
    """
    return await _fetch_url_with_metadata_internal(url, config, timeout)


async def main():
    logger.info("Hello from Web Browsing MCP Server!")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
