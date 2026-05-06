"""Configuration management for the web browsing MCP server."""

import os

# Environment variable names
ENV_CONTEXT_LIMIT = "WEB_MCP_CONTEXT_LIMIT"
ENV_REQUEST_TIMEOUT = "WEB_MCP_REQUEST_TIMEOUT"
ENV_DEFAULT_EXTRACTOR = "WEB_MCP_DEFAULT_EXTRACTOR"
ENV_INCLUDE_METADATA = "WEB_MCP_INCLUDE_METADATA"
ENV_INCLUDE_LINKS = "WEB_MCP_INCLUDE_LINKS"
ENV_INCLUDE_COMMENTS = "WEB_MCP_INCLUDE_COMMENTS"
ENV_ENABLE_TOKEN_ESTIMATION = "WEB_MCP_ENABLE_TOKEN_ESTIMATION"
ENV_TRUNCATION_STRATEGY = "WEB_MCP_TRUNCATION_STRATEGY"
ENV_SEARXNG_URL = "WEB_MCP_SEARXNG_URL"
ENV_USER_AGENT = "WEB_MCP_USER_AGENT"
ENV_MAX_CONTENT_LENGTH = "WEB_MCP_MAX_CONTENT_LENGTH"
ENV_CACHE_TTL = "WEB_MCP_CACHE_TTL"
ENV_PLAYWRIGHT_ENABLED = "WEB_MCP_PLAYWRIGHT_ENABLED"
ENV_PLAYWRIGHT_TIMEOUT = "WEB_MCP_PLAYWRIGHT_TIMEOUT"
ENV_PLAYWRIGHT_FALLBACK_THRESHOLD = "WEB_MCP_PLAYWRIGHT_FALLBACK_THRESHOLD"
ENV_PUBLIC_URL = "WEB_MCP_PUBLIC_URL"
ENV_AUTH_TOKEN = "WEB_MCP_AUTH_TOKEN"
ENV_CONTENT_TTL = "WEB_MCP_CONTENT_TTL"
ENV_CONTENT_STORAGE_PATH = "WEB_MCP_CONTENT_STORAGE_PATH"
# PDF settings
ENV_PDF_CHARS_PER_PAGE = "WEB_MCP_PDF_CHARS_PER_PAGE"

# JavaScript execution settings
ENV_JS_FETCH_MAX_RESPONSE_SIZE = "WEB_MCP_JS_FETCH_MAX_RESPONSE_SIZE"
ENV_JS_FETCH_MAX_REQUESTS = "WEB_MCP_JS_FETCH_MAX_REQUESTS"
ENV_JS_FETCH_MAX_TOTAL_BYTES = "WEB_MCP_JS_FETCH_MAX_TOTAL_BYTES"
ENV_JS_FETCH_TIMEOUT = "WEB_MCP_JS_FETCH_TIMEOUT"
ENV_JS_FETCH_VERIFY_SSL = "WEB_MCP_JS_FETCH_VERIFY_SSL"
ENV_JS_EXECUTION_TIMEOUT = "WEB_MCP_JS_EXECUTION_TIMEOUT"

# Valid extractor types
VALID_EXTRACTORS = {"trafilatura", "readability", "custom"}


class Config:
    """Configuration for the web browsing MCP server."""

    def __init__(self):
        # Context limit in tokens (default 120k)
        self.max_tokens: int = self._validate_int(
            os.environ.get(ENV_CONTEXT_LIMIT, "120000"), 1000, 1000000
        )

        # Request timeout in seconds
        self.request_timeout: int = self._validate_int(
            os.environ.get(ENV_REQUEST_TIMEOUT, "30"), 1, 300
        )

        # Default extractor to use
        self.default_extractor: str = os.environ.get(ENV_DEFAULT_EXTRACTOR, "trafilatura")
        self._validate_extractor()

        # Whether to include metadata
        self.include_metadata: bool = os.environ.get(ENV_INCLUDE_METADATA, "true").lower() in (
            "true",
            "1",
            "yes",
        )

        # Whether to include links
        self.include_links: bool = os.environ.get(ENV_INCLUDE_LINKS, "false").lower() in (
            "true",
            "1",
            "yes",
        )

        # Whether to include comments
        self.include_comments: bool = os.environ.get(ENV_INCLUDE_COMMENTS, "false").lower() in (
            "true",
            "1",
            "yes",
        )

        # Whether to use token estimation
        self.enable_token_estimation: bool = os.environ.get(
            ENV_ENABLE_TOKEN_ESTIMATION, "true"
        ).lower() in ("true", "1", "yes")

        # Truncation strategy: "smart" or "simple"
        self.truncation_strategy: str = os.environ.get(ENV_TRUNCATION_STRATEGY, "smart")

        # SearXNG configuration
        self.searxng_url: str | None = os.environ.get(ENV_SEARXNG_URL, None)

        # User-Agent header for requests (default with GitHub URL)
        self.user_agent: str = os.environ.get(
            ENV_USER_AGENT,
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        )

        # Maximum content length in bytes (default 10MB)
        self.max_content_length: int = self._validate_int(
            os.environ.get(ENV_MAX_CONTENT_LENGTH, "10485760"), 1, 1073741824
        )

        # Cache TTL in seconds (default 3600s = 1 hour)
        self.cache_ttl: int = self._validate_int(os.environ.get(ENV_CACHE_TTL, "3600"), 1, 86400)

        # Playwright settings
        self.playwright_enabled: bool = os.environ.get(ENV_PLAYWRIGHT_ENABLED, "true").lower() in (
            "true",
            "1",
            "yes",
        )

        self.playwright_timeout: int = self._validate_int(
            os.environ.get(ENV_PLAYWRIGHT_TIMEOUT, "30000"), 5000, 120000
        )

        # Minimum content length to consider httpx fetch successful (default 500 chars)
        # Below this, fallback to playwright
        self.playwright_fallback_threshold: int = self._validate_int(
            os.environ.get(ENV_PLAYWRIGHT_FALLBACK_THRESHOLD, "500"), 0, 100000
        )

        self.public_url: str | None = os.environ.get(ENV_PUBLIC_URL, None)
        if self.public_url:
            self.public_url = self.public_url.rstrip("/")

        self.auth_token: str | None = os.environ.get(ENV_AUTH_TOKEN, None)

        # Content TTL: 0 means endless (never expire), otherwise 60-86400 seconds
        content_ttl_str = os.environ.get(ENV_CONTENT_TTL, "3600") or "3600"
        try:
            content_ttl_val = int(content_ttl_str)
            if content_ttl_val == 0:
                self.content_ttl: int = 0
            else:
                self.content_ttl = self._validate_int(content_ttl_str, 60, 86400)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid content_ttl value: {content_ttl_str}")

        self.content_storage_path: str = os.environ.get(ENV_CONTENT_STORAGE_PATH, "/data/content")

        # PDF settings
        self.pdf_chars_per_page: int = self._validate_int(
            os.environ.get(ENV_PDF_CHARS_PER_PAGE, "60000"), 10000, 500000
        )

        # JavaScript execution settings
        self.js_fetch_max_response_size: int = self._validate_int(
            os.environ.get(ENV_JS_FETCH_MAX_RESPONSE_SIZE, "5242880"),
            1024,
            104857600,  # 5MB default, max 100MB
        )

        self.js_fetch_max_requests: int = self._validate_int(
            os.environ.get(ENV_JS_FETCH_MAX_REQUESTS, "10"),
            1,
            100,  # max 10 fetches per execution
        )

        self.js_fetch_max_total_bytes: int = self._validate_int(
            os.environ.get(ENV_JS_FETCH_MAX_TOTAL_BYTES, "10485760"),
            1024,
            104857600,  # 10MB total per execution
        )

        self.js_fetch_timeout: int = self._validate_int(
            os.environ.get(ENV_JS_FETCH_TIMEOUT, "10000"),
            1000,
            60000,  # 10s default per fetch
        )

        self.js_fetch_verify_ssl: bool = os.environ.get(
            ENV_JS_FETCH_VERIFY_SSL, "true"
        ).lower() in ("true", "1", "yes")

        self.js_execution_timeout: int = self._validate_int(
            os.environ.get(ENV_JS_EXECUTION_TIMEOUT, "30000"),
            1000,
            300000,  # 30s default max execution
        )

    @property
    def http_headers(self) -> dict[str, str]:
        """Standard browser-like HTTP headers for outgoing requests."""
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,pl;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    def _validate_int(self, value: str | None, min_val: int, max_val: int) -> int:
        """Validate integer configuration value.

        Args:
            value: The string value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value

        Returns:
            Validated integer value

        Raises:
            ValueError: If the value is invalid
        """
        try:
            int_val = int(value)
            if min_val <= int_val <= max_val:
                return int_val
            raise ValueError(f"Value must be between {min_val} and {max_val}")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid configuration value: {e}")

    def _validate_extractor(self) -> None:
        """Validate the default extractor setting.

        Raises:
            ValueError: If the extractor is not valid
        """
        if self.default_extractor not in VALID_EXTRACTORS:
            raise ValueError(
                f"Invalid extractor: {self.default_extractor}. "
                f"Must be one of: {', '.join(VALID_EXTRACTORS)}"
            )

    @property
    def max_chars(self) -> int:
        """Estimate maximum characters based on token limit.

        Rough estimate: 1 token ≈ 4 characters
        """
        return self.max_tokens * 4


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        The global Config instance
    """
    global _config

    if _config is None:
        _config = Config()

    return _config


def reset_config() -> None:
    """Reset the global config. For testing purposes."""
    global _config
    _config = None


def validate_config() -> bool:
    """Validate all configuration values.

    Returns:
        True if config is valid

    Raises:
        ValueError: If any configuration value is invalid
    """
    try:
        config = Config()
        # Access all properties to trigger validation
        _ = config.max_tokens
        _ = config.request_timeout
        _ = config.default_extractor
        _ = config.max_chars
        return True
    except ValueError as e:
        raise ValueError(f"Configuration validation failed: {e}")
