"""Security utilities for the web browsing MCP server."""

import ipaddress
import os
import re
import socket
import time

from web_mcp.logging_utils import get_logger

logger = get_logger(__name__)

# URL validation patterns
URL_PATTERN = re.compile(
    r'^https?://[a-zA-Z0-9]([a-zA-Z0-9\-\.]{1,253}[a-zA-Z0-9])?(\:[0-9]{1,5})?(/[^\s<>"{}|\\^`\[\]]*)?(\?[^\s<>"{}|\\^`\[\]]*)?$'
)

# Valid URL schemes
VALID_SCHEMES = {"http", "https"}

# Default whitelist (can be overridden via environment)
DEFAULT_WHITELIST: set[str] = {
    "wikipedia.org",
    "github.com",
    "stackoverflow.com",
}

# Default blacklist
DEFAULT_BLACKLIST: set[str] = {
    "malware.example.com",
}

# Environment variable names
ENV_RATE_LIMIT_REQUESTS = "WEB_MCP_RATE_LIMIT_REQUESTS"
ENV_RATE_LIMIT_WINDOW = "WEB_MCP_RATE_LIMIT_WINDOW"

# Private IPv4 networks that should be blocked (SSRF protection)
IPV4_BLACKLIST = [
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("10.0.0.0/8"),  # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),  # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),  # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local
    ipaddress.ip_network("0.0.0.0/8"),  # Current network
]

# Private IPv6 networks that should be blocked (SSRF protection)
IPV6_BLACKLIST = [
    ipaddress.ip_network("::1/128"),  # Loopback
    ipaddress.ip_network("fe80::/10"),  # Link-local
    ipaddress.ip_network("fc00::/7"),  # Unique local
]


def validate_url(url: str) -> bool:
    """Validate a URL.

    Args:
        url: The URL to validate

    Returns:
        True if the URL is valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    # Check scheme
    if not any(url.startswith(f"{scheme}://") for scheme in VALID_SCHEMES):
        return False

    # Check against pattern
    return URL_PATTERN.match(url) is not None


def is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private/reserved range.

    Args:
        ip: IP address string

    Returns:
        True if the IP is private or reserved
    """
    try:
        ip_obj = ipaddress.ip_address(ip)

        # Check IPv4 blacklists
        for network in IPV4_BLACKLIST:
            if ip_obj in network:
                return True

        # Check IPv6 blacklists
        return any(ip_obj in network for network in IPV6_BLACKLIST)
    except ValueError:
        # Invalid IP address format - block as safety measure
        return True


def validate_url_ip(url: str) -> bool:
    """Validate that a URL does not resolve to private IPs.

    This performs DNS resolution and checks the resulting IP addresses
    to prevent SSRF attacks via private/internal network access.

    Args:
        url: The URL to validate

    Returns:
        True if all resolved IPs are public, False otherwise
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            logger.warning(f"No hostname found in URL: {url}")
            return False

        # Resolve all IP addresses (both IPv4 and IPv6)
        addr_info = socket.getaddrinfo(hostname, None)

        for _family, _, _, _, sockaddr in addr_info:
            ip = sockaddr[0]
            if is_private_ip(ip):
                logger.warning(f"SSRF attempt blocked: {url} resolves to private IP {ip}")
                return False

        return True
    except socket.gaierror as e:
        # DNS resolution failed - block for safety
        logger.error(f"DNS resolution failed for URL: {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error validating URL IP for {url}: {e}")
        return False


def validate_url_no_credentials(url: str) -> bool:
    """Validate that a URL does not contain credentials.

    This prevents credential injection attacks where URLs like
    'https://wikipedia.org@evil.com' could bypass domain validation.

    Args:
        url: The URL to validate

    Returns:
        True if the URL has no credentials, False otherwise
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)

        # Check for username or password in URL
        if parsed.username or parsed.password:
            logger.warning(f"URL with credentials rejected: {url}")
            return False

        # Also check for @ symbol in netloc (bypass attempt detection)
        if "@" in (parsed.netloc or ""):
            logger.warning(f"URL credential injection detected: {url}")
            return False

        return True
    except Exception as e:
        logger.error(f"Error validating URL credentials for {url}: {e}")
        return False


def validate_url_with_whitelist(url: str, whitelist: set[str] | None = None) -> bool:
    """Validate URL against a whitelist.

    Args:
        url: The URL to validate
        whitelist: Set of allowed domains. If None, uses DEFAULT_WHITELIST

    Returns:
        True if the URL is valid and whitelisted
    """
    if not validate_url(url):
        return False

    if whitelist is None:
        whitelist = DEFAULT_WHITELIST

    # Extract domain from URL
    try:
        url_without_scheme = url.split("://", 1)[1]
        domain = url_without_scheme.split("/")[0].lower()

        for allowed_domain in whitelist:
            if domain == allowed_domain.lower() or domain.endswith("." + allowed_domain.lower()):
                return True
    except (IndexError, ValueError):
        return False

    return False


def validate_url_with_blacklist(url: str, blacklist: set[str] | None = None) -> bool:
    """Validate URL against a blacklist.

    Args:
        url: The URL to validate
        blacklist: Set of blocked domains. If None, uses DEFAULT_BLACKLIST

    Returns:
        True if the URL is valid and not blacklisted
    """
    if not validate_url(url):
        return False

    if blacklist is None:
        blacklist = DEFAULT_BLACKLIST

    try:
        url_without_scheme = url.split("://", 1)[1]
        domain = url_without_scheme.split("/")[0].lower()

        for blocked_domain in blacklist:
            if domain == blocked_domain.lower() or domain.endswith("." + blocked_domain.lower()):
                return False
    except (IndexError, ValueError):
        pass

    return True


def sanitize_input(text: str | None) -> str:
    """Sanitize user input to prevent injection attacks.

    Args:
        text: The text to sanitize

    Returns:
        Sanitized text
    """
    if not text or not isinstance(text, str):
        return ""

    # Remove null bytes
    text = text.replace("\x00", "")

    # Remove control characters (except newlines and tabs)
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Remove HTML tags to prevent XSS
    text = re.sub(r"<[^>]+>", "", text)

    # Limit length
    max_length = 10000
    if len(text) > max_length:
        text = text[:max_length]

    return text


class RateLimiter:
    """Simple rate limiter using sliding window."""

    def __init__(self, max_requests: int = 10, window_seconds: float = 60.0):
        """Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests: int = max_requests
        self.window_seconds: float = window_seconds
        self._requests: list[float] = []

    def is_allowed(self) -> bool:
        """Check if a request is allowed.

        Returns:
            True if the request is allowed, False otherwise
        """
        current_time = time.time()

        # Remove old requests outside the window
        self._requests = [
            req_time for req_time in self._requests if current_time - req_time < self.window_seconds
        ]

        # Check if under limit
        if len(self._requests) >= self.max_requests:
            return False

        # Record this request
        self._requests.append(current_time)
        return True

    def get_remaining_requests(self) -> int:
        """Get the number of remaining requests in the current window.

        Returns:
            Number of remaining requests
        """
        current_time = time.time()

        # Remove old requests
        self._requests = [
            req_time for req_time in self._requests if current_time - req_time < self.window_seconds
        ]

        return max(0, self.max_requests - len(self._requests))

    def reset(self) -> None:
        """Reset the rate limiter."""
        self._requests.clear()


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter.

    Returns:
        The global rate limiter instance
    """
    global _rate_limiter

    if _rate_limiter is None:
        max_requests = int(os.environ.get(ENV_RATE_LIMIT_REQUESTS, "10"))
        window_seconds = float(os.environ.get(ENV_RATE_LIMIT_WINDOW, "60"))
        _rate_limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)

    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter. For testing purposes."""
    global _rate_limiter
    _rate_limiter = None
