"""TLS-based URL fetching using tls-client for realistic browser fingerprints.

Wraps the synchronous tls-client library (Go-based) to provide HTTP requests
with a Chrome-like TLS fingerprint (JA3/JA4), bypassing anti-bot systems that
check the TLS handshake rather than just HTTP headers.
"""

import asyncio
from typing import Any, Dict, Optional

from web_mcp.logging_utils import get_logger

logger = get_logger(__name__)


class TlsFetchError(Exception):
    """Exception raised when tls-client fetch fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _is_tls_error_retryable(error: Exception) -> bool:
    """Check if a tls-client error is retryable."""
    error_str = str(error).lower()
    return any(
        keyword in error_str
        for keyword in [
            "connection",
            "timeout",
            "refused",
            "reset",
            "closed",
            "network",
            "dns",
            "resolve",
        ]
    )


def _fetch_with_tls_sync(
    url: str,
    headers: Dict[str, str],
    client_identifier: str = "chrome120",
    timeout_seconds: int = 30,
) -> str:
    """Synchronous tls-client fetch (runs in threadpool).

    Args:
        url: The URL to fetch
        headers: HTTP headers to send
        client_identifier: TLS fingerprint preset (default Chrome 120)
        timeout_seconds: Request timeout in seconds

    Returns:
        Response text content

    Raises:
        TlsFetchError: If the request fails
    """
    try:
        import tls_client
    except ImportError:
        raise TlsFetchError("tls-client is not installed")

    session = tls_client.Session(client_identifier=client_identifier)
    session.timeout = timeout_seconds

    try:
        response = session.get(url, headers=headers)
    except Exception as e:
        if _is_tls_error_retryable(e):
            raise TlsFetchError(f"Network error: {e}")
        raise TlsFetchError(f"Request failed: {e}")

    status_code = response.status_code
    if status_code >= 400:
        raise TlsFetchError(
            f"HTTP {status_code} from {url}"
        )

    return response.text


async def fetch_with_tls(
    url: str,
    headers: Dict[str, str],
    client_identifier: str = "chrome120",
    timeout_seconds: int = 30,
) -> str:
    """Fetch URL using tls-client with Chrome TLS fingerprint.

    Runs the synchronous tls-client in a threadpool to avoid blocking
    the async event loop.

    Args:
        url: The URL to fetch
        headers: HTTP headers to send (overrides tls-client defaults)
        client_identifier: TLS fingerprint preset (default Chrome 120)
        timeout_seconds: Request timeout in seconds

    Returns:
        Response text content

    Raises:
        TlsFetchError: If the request fails
    """
    return await asyncio.to_thread(
        _fetch_with_tls_sync,
        url,
        headers,
        client_identifier,
        timeout_seconds,
    )


async def fetch_with_tls_raw(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    client_identifier: str = "chrome120",
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """Fetch URL using tls-client and return full response metadata.

    Args:
        url: The URL to fetch
        headers: HTTP headers to send
        client_identifier: TLS fingerprint preset
        timeout_seconds: Request timeout in seconds

    Returns:
        Dict with 'content', 'status_code', and 'headers' keys
    """
    import asyncio

    try:
        import tls_client
    except ImportError:
        raise TlsFetchError("tls-client is not installed")

    session = tls_client.Session(client_identifier=client_identifier)
    session.timeout = timeout_seconds

    try:
        response = await asyncio.to_thread(
            session.get, url, headers=headers or {}
        )
    except Exception as e:
        if _is_tls_error_retryable(e):
            raise TlsFetchError(f"Network error: {e}")
        raise TlsFetchError(f"Request failed: {e}")

    return {
        "content": response.text,
        "status_code": response.status_code,
        "headers": dict(response.headers) if hasattr(response, "headers") else {},
    }
