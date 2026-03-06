"""Unit tests for the fetcher module."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from web_mcp.fetcher import ContentLengthExceededError, FetchError, fetch_url


class TestFetchUrl:
    """Tests for the fetch_url function."""

    @pytest.mark.asyncio
    async def test_fetch_url_success(self):
        """Test successful URL fetch."""
        mock_response = MagicMock()
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            result = await fetch_url("https://example.com", config)

            assert "Test content" in result
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_url_timeout(self):
        """Test fetch with timeout error."""
        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 5
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            with pytest.raises(FetchError) as exc_info:
                await fetch_url("https://example.com", config)

            assert "Request timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_url_http_error(self):
        """Test fetch with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "404 Not Found", request=MagicMock(), response=mock_response
                )
            )
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            with pytest.raises(FetchError) as exc_info:
                await fetch_url("https://example.com", config)

            assert "HTTP error 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_url_request_error(self):
        """Test fetch with request error."""
        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            with pytest.raises(FetchError) as exc_info:
                await fetch_url("https://example.com", config)

            assert "Request failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fetch_url_invalid_url(self):
        """Test fetch with invalid URL."""
        config = MagicMock()
        config.request_timeout = 30

        # This should raise an error since the URL is invalid
        with pytest.raises(Exception):
            await fetch_url("not-a-valid-url", config)

    @pytest.mark.asyncio
    async def test_fetch_url_with_custom_timeout(self):
        """Test fetch with custom timeout."""
        mock_response = MagicMock()
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 60
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            result = await fetch_url("https://example.com", config)

            assert "Test" in result

    @pytest.mark.asyncio
    async def test_fetch_url_connection_error(self):
        """Test fetch with connection error."""
        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection refused"))
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            with pytest.raises(FetchError) as exc_info:
                await fetch_url("https://example.com", config)

            assert "Connection refused" in str(exc_info.value)


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


class TestRetryLogic:
    """Tests for retry logic in fetch_url function."""

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Test that connection errors trigger retries."""

        mock_response = MagicMock()
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            # First call raises connection error, second succeeds
            mock_client = MagicMock()
            mock_client.get = AsyncMock(
                side_effect=[httpx.ConnectError("Connection refused"), mock_response]
            )
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            # This should succeed after retrying
            result = await fetch_url("https://example.com", config)

            # Verify it was called twice (initial + 1 retry)
            assert mock_client.get.call_count == 2
            assert "Test content" in result

    @pytest.mark.asyncio
    async def test_retry_on_timeout_error(self):
        """Test that timeout errors trigger retries."""
        mock_response = MagicMock()
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            # First call times out, second succeeds
            mock_client = MagicMock()
            mock_client.get = AsyncMock(
                side_effect=[httpx.TimeoutException("Request timed out"), mock_response]
            )
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            result = await fetch_url("https://example.com", config)

            # Verify it was called twice
            assert mock_client.get.call_count == 2
            assert "Test content" in result

    @pytest.mark.asyncio
    async def test_retry_on_5xx_error(self):
        """Test that 5xx server errors trigger retries."""
        mock_response = MagicMock()
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            # First call returns 500, second succeeds
            mock_client = MagicMock()
            mock_client.get = AsyncMock(
                side_effect=[
                    httpx.HTTPStatusError(
                        "500 Internal Server Error",
                        request=MagicMock(),
                        response=MagicMock(status_code=500),
                    ),
                    mock_response,
                ]
            )
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            await fetch_url("https://example.com", config)

            # Verify it was called twice
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_429_rate_limit(self):
        """Test that 429 rate limit errors trigger retries."""
        mock_response = MagicMock()
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            # First call returns 429, second succeeds
            mock_client = MagicMock()
            mock_client.get = AsyncMock(
                side_effect=[
                    httpx.HTTPStatusError(
                        "429 Too Many Requests",
                        request=MagicMock(),
                        response=MagicMock(status_code=429),
                    ),
                    mock_response,
                ]
            )
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            await fetch_url("https://example.com", config)

            # Verify it was called twice
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx_error(self):
        """Test that 4xx errors (except 429) do NOT trigger retries."""
        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()
            # Return 404 immediately
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "404 Not Found", request=MagicMock(), response=MagicMock(status_code=404)
                )
            )
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            with pytest.raises(FetchError) as exc_info:
                await fetch_url("https://example.com", config)

            # Verify it was called only once (no retry)
            assert mock_client.get.call_count == 1
            assert "HTTP error 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_retry_on_403_forbidden(self):
        """Test that 403 Forbidden errors do NOT trigger retries."""
        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "403 Forbidden", request=MagicMock(), response=MagicMock(status_code=403)
                )
            )
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            with pytest.raises(FetchError) as exc_info:
                await fetch_url("https://example.com", config)

            # Verify it was called only once (no retry)
            assert mock_client.get.call_count == 1
            assert "HTTP error 403" in str(exc_info.value)


class TestResponseSizeLimiting:
    """Tests for response size limiting in fetch_url function."""

    @pytest.mark.asyncio
    async def test_block_response_exceeding_max_length(self):
        """Test that responses exceeding max_content_length are blocked."""
        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()

            # Create a response that exceeds the limit
            mock_response = MagicMock()
            mock_response.headers = {"content-length": "1000"}  # Header says 1000 bytes
            mock_response.status_code = 200

            # Stream content that exceeds limit
            async def mock_aiter_text():
                yield "a" * 10000  # More than max_content_length

            mock_response.aiter_text = mock_aiter_text
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 1000  # Very small limit
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            with pytest.raises(ContentLengthExceededError) as exc_info:
                await fetch_url("https://example.com", config)

            assert "exceeds maximum allowed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_allow_response_within_limit(self):
        """Test that responses within max_content_length are allowed."""
        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()

            mock_response = MagicMock()
            mock_response.headers = {"content-length": "100"}  # Header says 100 bytes
            mock_response.text = "<html><body>Test</body></html>"
            mock_response.raise_for_status = MagicMock()

            async def mock_aiter_text():
                yield "<html><body>Test</body></html>"  # Less than limit

            mock_response.aiter_text = mock_aiter_text
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10000  # Large enough limit
            config.user_agent = "TestAgent/1.0"
            config.cache_ttl = 3600

            result = await fetch_url("https://example.com", config)

            assert "Test" in result


class TestUserAgentHeader:
    """Tests for User-Agent header handling in fetch_url function."""

    @pytest.mark.asyncio
    async def test_custom_user_agent_is_sent(self):
        """Test that custom User-Agent header is sent with requests."""
        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()

            mock_response = MagicMock()
            mock_response.text = "<html><body>Test</body></html>"
            mock_response.raise_for_status = MagicMock()

            async def mock_aiter_text():
                yield "<html><body>Test</body></html>"

            mock_response.aiter_text = mock_aiter_text
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            config.user_agent = "CustomBot/2.0 (+https://example.com/bot)"
            config.cache_ttl = 3600

            await fetch_url("https://example.com", config)

            # Verify the request was made with the custom User-Agent
            mock_client.get.assert_called_once()
            call_kwargs = mock_client.get.call_args[1]
            assert "headers" in call_kwargs
            assert (
                call_kwargs["headers"]["User-Agent"] == "CustomBot/2.0 (+https://example.com/bot)"
            )

    @pytest.mark.asyncio
    async def test_user_agent_configurable_via_config(self):
        """Test that User-Agent is configurable via config object."""
        with patch("web_mcp.fetcher.get_connection_pool") as mock_get_pool:
            mock_client = MagicMock()

            mock_response = MagicMock()
            mock_response.text = "<html><body>Test</body></html>"
            mock_response.raise_for_status = MagicMock()

            async def mock_aiter_text():
                yield "<html><body>Test</body></html>"

            mock_response.aiter_text = mock_aiter_text
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_pool.return_value = mock_client

            config = MagicMock()
            config.request_timeout = 30
            config.max_content_length = 10485760
            # Use default User-Agent from config
            config.user_agent = "WebMCP/1.0 (+https://github.com/yourorg/web-mcp)"
            config.cache_ttl = 3600

            await fetch_url("https://example.com", config)

            call_kwargs = mock_client.get.call_args[1]
            assert (
                call_kwargs["headers"]["User-Agent"]
                == "WebMCP/1.0 (+https://github.com/yourorg/web-mcp)"
            )
