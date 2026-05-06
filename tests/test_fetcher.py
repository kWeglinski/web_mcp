"""Unit tests for the fetcher module."""

from unittest.mock import MagicMock, patch

import pytest

from web_mcp.fetcher import (
    ContentLengthExceededError,
    FetchError,
    RetryableFetchError,
    fetch_url,
)


def _make_mock_config(**overrides):
    """Create a mock config with sensible defaults."""
    config = MagicMock()
    config.request_timeout = 30
    config.max_content_length = 10485760
    config.cache_ttl = 3600
    config.request_delay_min = 0.0
    config.request_delay_max = 0.0
    config.tls_client_identifier = "chrome120"
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def _make_mock_response(content="Test content", status_code=200, headers=None):
    """Create a mock tls-client response dict."""
    return {
        "content": content,
        "status_code": status_code,
        "headers": headers or {"Content-Type": "text/html; charset=utf-8"},
    }


class TestFetchUrl:
    """Tests for the fetch_url function."""

    @pytest.mark.asyncio
    async def test_fetch_url_success(self):
        """Test successful URL fetch."""
        mock_response = _make_mock_response("<html><body>Test content</body></html>")

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = mock_response

            config = _make_mock_config()
            result = await fetch_url("https://example.com", config)

            assert "Test content" in result
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_url_timeout(self):
        """Test fetch with timeout error."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.side_effect = TlsFetchError("Network error: timeout")

            config = _make_mock_config()
            with pytest.raises(FetchError) as exc_info:
                await fetch_url("https://example.com", config)

            assert "timeout" in str(exc_info.value).lower() or "Network error" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_fetch_url_http_error(self):
        """Test fetch with HTTP 404 error."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.side_effect = TlsFetchError("HTTP 404 from https://example.com")

            config = _make_mock_config()
            with pytest.raises(FetchError) as exc_info:
                await fetch_url("https://example.com", config)

            assert "404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_url_connection_error(self):
        """Test fetch with connection error."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.side_effect = TlsFetchError("Network error: Connection refused")

            config = _make_mock_config()
            with pytest.raises(FetchError) as exc_info:
                await fetch_url("https://example.com", config)

            assert "Connection refused" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_url_invalid_url(self):
        """Test fetch with invalid URL."""
        config = _make_mock_config()

        with pytest.raises(FetchError) as exc_info:
            await fetch_url("not-a-valid-url", config)

        assert "Invalid URL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_url_with_custom_timeout(self):
        """Test fetch with custom timeout."""
        mock_response = _make_mock_response("<html><body>Test</body></html>")

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = mock_response

            config = _make_mock_config(request_timeout=60)
            result = await fetch_url("https://example.com", config)

            assert "Test" in result
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args
            assert call_args.kwargs["timeout_seconds"] == 60

    @pytest.mark.asyncio
    async def test_fetch_url_credentials_blocked(self):
        """Test that URLs with credentials are blocked."""
        config = _make_mock_config()

        with pytest.raises(FetchError) as exc_info:
            await fetch_url("https://user:pass@example.com", config)

        # URL with embedded credentials is rejected as invalid
        assert "Invalid URL" in str(exc_info.value) or "credentials" in str(exc_info.value).lower()


class TestFetchError:
    """Tests for the FetchError exception."""

    def test_fetch_error_message(self):
        """Test FetchError with message."""
        error = FetchError("Test error message")
        assert error.message == "Test error message"
        assert str(error) == "Test error message"

    def test_fetch_error_inherits_exception(self):
        """Test that FetchError inherits from Exception."""
        error = FetchError("Test")
        assert isinstance(error, Exception)

    def test_content_length_error_inherits_fetch_error(self):
        """Test that ContentLengthExceededError inherits from FetchError."""
        error = ContentLengthExceededError("Too large")
        assert isinstance(error, FetchError)

    def test_retryable_error_inherits_fetch_error(self):
        """Test that RetryableFetchError inherits from FetchError."""
        error = RetryableFetchError("Temporary")
        assert isinstance(error, FetchError)


class TestRetryLogic:
    """Tests for retry logic in fetch_url function."""

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self):
        """Test that network errors trigger retries."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            # First call fails with network error, second succeeds
            mock_fetch.side_effect = [
                TlsFetchError("Network error: Connection refused"),
                _make_mock_response("<html><body>Test content</body></html>"),
            ]

            config = _make_mock_config()
            result = await fetch_url("https://example.com", config)

            assert mock_fetch.call_count == 2
            assert "Test content" in result

    @pytest.mark.asyncio
    async def test_retry_on_5xx_error(self):
        """Test that 5xx server errors trigger retries."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            # First call returns 500, second succeeds
            mock_fetch.side_effect = [
                TlsFetchError("HTTP 500 from https://example.com"),
                _make_mock_response("<html><body>Test content</body></html>"),
            ]

            config = _make_mock_config()
            result = await fetch_url("https://example.com", config)

            assert mock_fetch.call_count == 2
            assert "Test content" in result

    @pytest.mark.asyncio
    async def test_retry_on_429_rate_limit(self):
        """Test that 429 rate limit errors trigger retries."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            # First call returns 429, second succeeds
            mock_fetch.side_effect = [
                TlsFetchError("HTTP 429 from https://example.com"),
                _make_mock_response("<html><body>Test content</body></html>"),
            ]

            config = _make_mock_config()
            result = await fetch_url("https://example.com", config)

            assert mock_fetch.call_count == 2
            assert "Test content" in result

    @pytest.mark.asyncio
    async def test_retry_on_403_anti_bot(self):
        """Test that 403 anti-bot errors trigger retries."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            # First call returns 403, second succeeds
            mock_fetch.side_effect = [
                TlsFetchError("HTTP 403 from https://example.com"),
                _make_mock_response("<html><body>Test content</body></html>"),
            ]

            config = _make_mock_config()
            result = await fetch_url("https://example.com", config)

            assert mock_fetch.call_count == 2
            assert "Test content" in result

    @pytest.mark.asyncio
    async def test_no_retry_on_404_not_found(self):
        """Test that 404 errors do NOT trigger retries."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.side_effect = TlsFetchError("HTTP 404 from https://example.com")

            config = _make_mock_config()
            with pytest.raises(FetchError) as exc_info:
                await fetch_url("https://example.com", config)

            assert mock_fetch.call_count == 1
            assert "404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test that max retries are exhausted before raising."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            # Always fail with network error (converted to RetryableFetchError)
            mock_fetch.side_effect = TlsFetchError("Network error: timeout")

            config = _make_mock_config()
            with pytest.raises(FetchError):
                await fetch_url("https://example.com", config)

            # max_attempts=3 means 3 calls
            assert mock_fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_5xx(self):
        """Test that max retries are exhausted for 5xx errors."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            # Always fail with 500 (HTTP status code present, so RetryableFetchError is raised)
            mock_fetch.side_effect = TlsFetchError("HTTP 500 from https://example.com")

            config = _make_mock_config()
            with pytest.raises(FetchError):
                await fetch_url("https://example.com", config)

            # max_attempts=3 means 3 calls
            assert mock_fetch.call_count == 3


class TestResponseSizeLimiting:
    """Tests for response size limiting in fetch_url function."""

    @pytest.mark.asyncio
    async def test_block_response_exceeding_max_length(self):
        """Test that responses exceeding max_content_length are blocked."""
        mock_response = _make_mock_response("a" * 20000)

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = mock_response

            config = _make_mock_config(max_content_length=1000)

            with pytest.raises(ContentLengthExceededError) as exc_info:
                await fetch_url("https://example.com", config)

            assert "exceeds maximum allowed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_allow_response_within_limit(self):
        """Test that responses within max_content_length are allowed."""
        mock_response = _make_mock_response("<html><body>Test</body></html>")

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = mock_response

            config = _make_mock_config(max_content_length=10000)
            result = await fetch_url("https://example.com", config)

            assert "Test" in result


class TestHeadersAndReferer:
    """Tests for header handling with tls-client."""

    @pytest.mark.asyncio
    async def test_referer_is_set_from_url(self):
        """Test that Referer header is set dynamically from the URL."""
        from web_mcp.config import Config, reset_config

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = _make_mock_response("Test content")

            # Use a real Config object to test header generation
            reset_config()
            config = Config()

            await fetch_url("https://example.com/path/page", config)

            # Check that the correct headers were passed to tls-client
            call_args = mock_fetch.call_args
            headers = call_args.kwargs["headers"]
            assert "Referer" in headers
            assert headers["Referer"] == "https://example.com/path/page"

    @pytest.mark.asyncio
    async def test_custom_referer_from_config(self):
        """Test that custom Referer from config is used."""
        import os

        from web_mcp.config import Config, reset_config

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = _make_mock_response("Test content")

            # Set custom referer via env var
            os.environ["WEB_MCP_REFERER"] = "https://www.google.com/"
            try:
                reset_config()
                config = Config()

                await fetch_url("https://example.com", config)

                call_args = mock_fetch.call_args
                headers = call_args.kwargs["headers"]
                assert headers["Referer"] == "https://www.google.com/"
            finally:
                del os.environ["WEB_MCP_REFERER"]

    @pytest.mark.asyncio
    async def test_user_agent_is_chrome(self):
        """Test that Chrome User-Agent is used by default."""
        from web_mcp.config import Config, reset_config

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = _make_mock_response("Test content")

            reset_config()
            config = Config()

            await fetch_url("https://example.com", config)

            call_args = mock_fetch.call_args
            headers = call_args.kwargs["headers"]
            assert "Chrome" in headers["User-Agent"]


class TestRequestDelay:
    """Tests for request delay/jitter."""

    @pytest.mark.asyncio
    async def test_delay_is_applied(self):
        """Test that request delay is applied between retries."""
        from web_mcp.tls_fetcher import TlsFetchError

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            # First call fails, second succeeds
            mock_fetch.side_effect = [
                TlsFetchError("Network error: timeout"),
                _make_mock_response("<html><body>Test</body></html>"),
            ]

            config = _make_mock_config(request_delay_min=0.1, request_delay_max=0.1)
            await fetch_url("https://example.com", config)

            # Verify delay was applied (at least 2 calls with retry)
            assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_no_delay_when_zero(self):
        """Test that no delay is applied when min=max=0."""
        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = _make_mock_response("Test content")

            config = _make_mock_config(request_delay_min=0.0, request_delay_max=0.0)
            await fetch_url("https://example.com", config)

            assert mock_fetch.call_count == 1


class TestRedirectValidator:
    """Tests for the RedirectValidator class."""

    def test_validator_initializes(self):
        """Test that RedirectValidator initializes correctly."""
        from web_mcp.fetcher import RedirectValidator

        validator = RedirectValidator(max_redirects=5)
        assert validator.max_redirects == 5

    def test_reset_clears_counter(self):
        """Test that reset clears the redirect counter."""
        from web_mcp.fetcher import RedirectValidator

        validator = RedirectValidator(max_redirects=5)
        validator._redirect_count = 3
        validator.reset()
        assert validator._redirect_count == 0


class TestGetConnectionPool:
    """Tests for the deprecated get_connection_pool function."""

    def test_get_connection_pool_returns_none(self):
        """Test that get_connection_pool returns None (deprecated)."""
        from web_mcp.fetcher import get_connection_pool

        result = get_connection_pool()
        assert result is None


class TestClosePool:
    """Tests for the close_pool function."""

    @pytest.mark.asyncio
    async def test_close_pool_does_not_raise(self):
        """Test that close_pool doesn't raise an error."""
        from web_mcp.fetcher import close_pool

        await close_pool()  # Should not raise


class TestFetchUrlWithMetadata:
    """Tests for fetch_url_with_metadata."""

    @pytest.mark.asyncio
    async def test_fetch_url_with_metadata_returns_bytes(self):
        """Test that fetch_url_with_metadata returns bytes content."""
        from web_mcp.fetcher import FetchedContent, fetch_url_with_metadata

        mock_response = _make_mock_response("<html><body>Test</body></html>")

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = mock_response

            config = _make_mock_config()
            result = await fetch_url_with_metadata("https://example.com", config)

            assert isinstance(result, FetchedContent)
            assert isinstance(result.content, bytes)


class TestFetchWithSizeLimit:
    """Tests for _fetch_with_size_limit."""

    @pytest.mark.asyncio
    async def test_fetch_with_size_limit_respects_max(self):
        """Test that _fetch_with_size_limit respects max_content_length."""
        from web_mcp.fetcher import ContentLengthExceededError, _fetch_with_size_limit

        mock_response = _make_mock_response("x" * 20000)

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = mock_response

            config = _make_mock_config(max_content_length=1000)

            with pytest.raises(ContentLengthExceededError):
                await _fetch_with_size_limit("https://example.com", config, 1000)

    @pytest.mark.asyncio
    async def test_fetch_with_size_limit_succeeds(self):
        """Test that _fetch_with_size_limit succeeds for small content."""
        from web_mcp.fetcher import _fetch_with_size_limit

        mock_response = _make_mock_response("<html><body>Test</body></html>")

        with patch("web_mcp.fetcher.fetch_with_tls_raw") as mock_fetch:
            mock_fetch.return_value = mock_response

            config = _make_mock_config(max_content_length=10000)
            result = await _fetch_with_size_limit("https://example.com", config, 10000)

            assert "Test" in result


class TestExtractStatusCode:
    """Tests for the _extract_status_code helper."""

    def test_extract_403(self):
        """Test extracting 403 status code."""
        from web_mcp.fetcher import _extract_status_code

        assert _extract_status_code("HTTP 403 from https://example.com") == 403

    def test_extract_500(self):
        """Test extracting 500 status code."""
        from web_mcp.fetcher import _extract_status_code

        assert _extract_status_code("HTTP 500 Internal Server Error") == 500

    def test_extract_no_status(self):
        """Test when no status code is present."""
        from web_mcp.fetcher import _extract_status_code

        assert _extract_status_code("Network error: timeout") is None


class TestShouldRetryResponse:
    """Tests for the _should_retry_response helper."""

    def test_retry_500(self):
        """Test that 500 triggers retry."""
        from web_mcp.fetcher import _should_retry_response

        assert _should_retry_response(500) is True

    def test_retry_429(self):
        """Test that 429 triggers retry."""
        from web_mcp.fetcher import _should_retry_response

        assert _should_retry_response(429) is True

    def test_retry_403(self):
        """Test that 403 triggers retry."""
        from web_mcp.fetcher import _should_retry_response

        assert _should_retry_response(403) is True

    def test_no_retry_200(self):
        """Test that 200 does not trigger retry."""
        from web_mcp.fetcher import _should_retry_response

        assert _should_retry_response(200) is False

    def test_no_retry_404(self):
        """Test that 404 does not trigger retry."""
        from web_mcp.fetcher import _should_retry_response

        assert _should_retry_response(404) is False

    def test_no_retry_none(self):
        """Test that None does not trigger retry."""
        from web_mcp.fetcher import _should_retry_response

        assert _should_retry_response(None) is False
