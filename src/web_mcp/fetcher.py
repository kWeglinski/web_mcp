"""URL fetching module for web browsing."""

from dataclasses import dataclass

import httpx

from web_mcp.cache import get_cache
from web_mcp.config import Config
from web_mcp.logging_utils import get_logger
from web_mcp.security import (
    validate_url,
    validate_url_ip,
    validate_url_no_credentials,
)
from web_mcp.utils.retry import with_retry

logger = get_logger(__name__)

_connection_pool: httpx.AsyncClient | None = None


def get_connection_pool() -> httpx.AsyncClient:
    """Get the global connection pool (httpx AsyncClient).

    Returns:
        The global httpx.AsyncClient instance
    """
    global _connection_pool

    if _connection_pool is None:
        _connection_pool = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
            timeout=httpx.Timeout(30.0),
        )

    return _connection_pool


def close_connection_pool() -> None:
    """Close the global connection pool."""
    global _connection_pool

    if _connection_pool is not None:
        import asyncio

        asyncio.run(_connection_pool.aclose())
        _connection_pool = None


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
    server errors (5xx), and rate limits (429).
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable.

    Args:
        error: The exception to check

    Returns:
        True if the error is retryable, False otherwise
    """
    if isinstance(error, httpx.ConnectError):
        return True

    if isinstance(error, httpx.TimeoutException):
        return True

    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        if 500 <= status_code < 600:
            return True
        if status_code == 429:
            return True

    return False


def _should_retry_response(response: httpx.Response) -> bool:
    """Check if a response with status code should be retried.

    Args:
        response: The HTTP response to check

    Returns:
        True if the response should be retried, False otherwise
    """
    status_code = response.status_code
    if 500 <= status_code < 600:
        return True
    return status_code == 429


async def _fetch_with_size_limit(
    client: httpx.AsyncClient, url: str, timeout: float, max_content_length: int, user_agent: str
) -> str:
    """Fetch URL with content length limiting.

    Args:
        client: The httpx AsyncClient instance
        url: The URL to fetch
        timeout: Request timeout in seconds
        max_content_length: Maximum content length in bytes
        user_agent: User-Agent header value

    Returns:
        Response text content

    Raises:
        ContentLengthExceededError: If content exceeds the limit
        FetchError: For other fetch errors
    """
    try:
        response = await client.get(
            url, timeout=timeout, follow_redirects=True, headers={"User-Agent": user_agent}
        )

        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                cl = int(content_length)
                if cl > max_content_length:
                    raise ContentLengthExceededError(
                        f"Content-Length ({cl} bytes) exceeds maximum allowed "
                        f"({max_content_length} bytes)"
                    )
            except ValueError:
                logger.warning(f"Invalid Content-Length header value: {content_length}")

        total_bytes = 0
        async for chunk in response.aiter_text():
            total_bytes += len(chunk)
            if total_bytes > max_content_length:
                raise ContentLengthExceededError(
                    f"Response size ({total_bytes} bytes) exceeds maximum allowed "
                    f"({max_content_length} bytes)"
                )

        response.raise_for_status()
        return response.text

    except httpx.TimeoutException as e:
        logger.error(f"Request timed out for URL {url}: {e}")
        raise RetryableFetchError(f"Request timed out: {e}")
    except ContentLengthExceededError:
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error for URL {url}: {e}")
        status_code = e.response.status_code
        if status_code == 429 or (500 <= status_code < 600):
            raise RetryableFetchError(f"HTTP error {status_code}: {e}")
        raise FetchError(f"HTTP error {status_code}: {e}")
    except httpx.RequestError as e:
        logger.error(f"Request failed for URL {url}: {e}")
        raise RetryableFetchError(f"Request failed: {e}")


class RedirectValidator:
    """Validates redirect targets before following.

    Ensures that each redirect target passes SSRF protection and
    whitelist/blacklist checks before being followed.
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


@dataclass
class _FetchResult:
    """Internal result of a fetch operation."""

    content: str | bytes
    content_type: str
    final_url: str
    response: httpx.Response


async def _fetch_core(
    url: str,
    config: Config,
    timeout: float | None = None,
    *,
    return_bytes: bool = False,
) -> _FetchResult:
    """Core fetch logic shared between text and bytes fetchers.

    Performs security validation, HTTP request, and content-length checking.
    Uses streaming to avoid loading large responses into memory unnecessarily.

    Args:
        url: The URL to fetch
        config: Configuration object
        timeout: Optional override for request timeout (httpx uses float)
        return_bytes: If True, return bytes; if False, return text

    Returns:
        _FetchResult with content, content-type, final URL, and response

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

    try:
        client = get_connection_pool()
        response = await client.get(
            url,
            timeout=request_timeout,
            follow_redirects=True,
            headers=config.http_headers,
        )

        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                cl = int(content_length)
                if cl > config.max_content_length:
                    raise ContentLengthExceededError(
                        f"Content-Length ({cl} bytes) exceeds maximum allowed "
                        f"({config.max_content_length} bytes)"
                    )
            except ValueError:
                logger.warning(f"Invalid Content-Length header value: {content_length}")

        if return_bytes:
            total_bytes = 0
            chunks: list[bytes] = []
            async for chunk in response.aiter_bytes():
                total_bytes += len(chunk)
                if total_bytes > config.max_content_length:
                    raise ContentLengthExceededError(
                        f"Response size ({total_bytes} bytes) exceeds maximum allowed "
                        f"({config.max_content_length} bytes)"
                    )
                chunks.append(chunk)
            content: str | bytes = b"".join(chunks)
        else:
            total_bytes = 0
            text_chunks: list[str] = []
            async for chunk in response.aiter_text():
                total_bytes += len(chunk)
                if total_bytes > config.max_content_length:
                    raise ContentLengthExceededError(
                        f"Response size ({total_bytes} bytes) exceeds maximum allowed "
                        f"({config.max_content_length} bytes)"
                    )
                text_chunks.append(chunk)
            content = "".join(text_chunks)

        response.raise_for_status()

        content_type = response.headers.get("content-type", "application/octet-stream")

        return _FetchResult(
            content=content,
            content_type=content_type,
            final_url=str(response.url),
            response=response,
        )

    except httpx.TimeoutException as e:
        logger.error(f"Request timed out for URL {url}: {e}")
        raise RetryableFetchError(f"Request timed out: {e}")
    except ContentLengthExceededError:
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error for URL {url}: {e}")
        status_code = e.response.status_code
        if status_code == 429 or (500 <= status_code < 600):
            raise RetryableFetchError(f"HTTP error {status_code}: {e}")
        raise FetchError(f"HTTP error {status_code}: {e}")
    except httpx.RequestError as e:
        logger.error(f"Request failed for URL {url}: {e}")
        raise RetryableFetchError(f"Request failed: {e}")


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
    retryable_exceptions=(httpx.ConnectError, httpx.TimeoutException, RetryableFetchError),
    jitter=True,
)
async def fetch_url(url: str, config: Config, timeout: float | None = None) -> str:
    """Fetch HTML content from a URL with security validation.

    This function performs comprehensive security checks before fetching:
    - URL format validation
    - Credential injection prevention
    - SSRF protection via DNS resolution and IP validation
    - Redirect validation to prevent SSRF via redirect chains

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
    """Fetch URL with httpx, fallback to Playwright for JS-heavy pages.

    First attempts to fetch with httpx. If the response is below the
    configured threshold (indicating possible JS-rendered content),
    falls back to Playwright for full browser rendering.

    Args:
        url: The URL to fetch
        config: Configuration object
        timeout: Optional override for request timeout

    Returns:
        HTML content (either from httpx or Playwright)

    Raises:
        FetchError: If both httpx and Playwright fail
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
            logger.info(f"httpx fetch failed, trying Playwright: {e}")
            try:
                return await fetch_with_playwright_cached(url, config)
            except PlaywrightFetchError as pe:
                logger.error(f"Playwright also failed: {pe}")
                raise e
        raise


async def close_pool() -> None:
    """Close the connection pool. For cleanup."""
    close_connection_pool()


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
    retryable_exceptions=(httpx.ConnectError, httpx.TimeoutException, RetryableFetchError),
    jitter=True,
)
async def fetch_url_with_metadata(
    url: str, config: Config, timeout: float | None = None
) -> FetchedContent:
    """Fetch URL content with content-type metadata.

    Returns both the raw content (as bytes) and the content-type header.
    This is useful for handling non-HTML content like PDFs.

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
