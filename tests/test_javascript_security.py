"""Tests for run_javascript tool security features."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from web_mcp.config import Config, reset_config


@pytest.fixture(autouse=True)
def reset_config_before_tests():
    """Reset config before and after each test."""
    reset_config()
    yield
    reset_config()


@pytest.fixture
def mock_config():
    """Create a mock config with default JS settings."""
    config = Config()
    config.js_fetch_max_requests = 10
    config.js_fetch_max_response_size = 5242880  # 5MB
    config.js_fetch_max_total_bytes = 10485760  # 10MB
    config.js_fetch_timeout = 10000
    config.js_fetch_verify_ssl = True
    config.js_execution_timeout = 30000
    return config


def create_mock_async_context(content=b"", status_code=200, headers=None, reason="OK"):
    """Helper to create a mock async context manager for httpx response."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.reason_phrase = reason
    mock_response.headers = headers or {"content-type": "text/plain"}
    if content:
        mock_response.headers["content-length"] = str(len(content))

    async def mock_aiter_bytes():
        if content:
            yield content

    mock_response.aiter_bytes = mock_aiter_bytes
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    return mock_response


def create_mock_client_with_response(mock_response):
    """Helper to create a mock AsyncClient that returns the given response."""
    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class TestJavascriptSSRFProtection:
    """Tests for SSRF protection in run_javascript fetch."""

    @pytest.mark.asyncio
    async def test_block_localhost_ip(self, mock_config):
        """Test that fetching 127.0.0.1 is blocked."""
        from web_mcp.server import run_javascript

        with patch("web_mcp.server.get_config", return_value=mock_config):
            result = await run_javascript(
                code="(await fetch('http://127.0.0.1/admin')).text()", timeout_ms=5000, context={}
            )

        assert "Error" in result or "private" in result.lower() or "restricted" in result.lower()

    @pytest.mark.asyncio
    async def test_block_private_ip_class_a(self, mock_config):
        """Test that fetching 10.x.x.x is blocked."""
        from web_mcp.server import run_javascript

        with patch("web_mcp.server.get_config", return_value=mock_config):
            result = await run_javascript(
                code="(await fetch('http://10.0.0.1/secret')).text()", timeout_ms=5000, context={}
            )

        assert "Error" in result or "private" in result.lower() or "restricted" in result.lower()

    @pytest.mark.asyncio
    async def test_block_private_ip_class_b(self, mock_config):
        """Test that fetching 172.16.x.x is blocked."""
        from web_mcp.server import run_javascript

        with patch("web_mcp.server.get_config", return_value=mock_config):
            result = await run_javascript(
                code="(await fetch('http://172.16.0.1/internal')).text()",
                timeout_ms=5000,
                context={},
            )

        assert "Error" in result or "private" in result.lower() or "restricted" in result.lower()

    @pytest.mark.asyncio
    async def test_block_private_ip_class_c(self, mock_config):
        """Test that fetching 192.168.x.x is blocked."""
        from web_mcp.server import run_javascript

        with patch("web_mcp.server.get_config", return_value=mock_config):
            result = await run_javascript(
                code="(await fetch('http://192.168.1.1/router')).text()",
                timeout_ms=5000,
                context={},
            )

        assert "Error" in result or "private" in result.lower() or "restricted" in result.lower()

    @pytest.mark.asyncio
    async def test_block_localhost_hostname(self, mock_config):
        """Test that fetching localhost hostname is blocked."""
        from web_mcp.server import run_javascript

        with patch("web_mcp.server.get_config", return_value=mock_config):
            result = await run_javascript(
                code="(await fetch('http://localhost:8080/api')).text()",
                timeout_ms=5000,
                context={},
            )

        assert "Error" in result or "private" in result.lower() or "restricted" in result.lower()

    @pytest.mark.asyncio
    async def test_block_invalid_scheme_ftp(self, mock_config):
        """Test that ftp:// URLs are blocked."""
        from web_mcp.server import run_javascript

        with patch("web_mcp.server.get_config", return_value=mock_config):
            result = await run_javascript(
                code="(await fetch('ftp://example.com/file')).text()", timeout_ms=5000, context={}
            )

        assert "Error" in result or "Invalid URL" in result

    @pytest.mark.asyncio
    async def test_block_invalid_scheme_file(self, mock_config):
        """Test that file:// URLs are blocked."""
        from web_mcp.server import run_javascript

        with patch("web_mcp.server.get_config", return_value=mock_config):
            result = await run_javascript(
                code="(await fetch('file:///etc/passwd')).text()", timeout_ms=5000, context={}
            )

        assert "Error" in result or "Invalid URL" in result

    @pytest.mark.asyncio
    async def test_block_invalid_scheme_javascript(self, mock_config):
        """Test that javascript: URLs are blocked."""
        from web_mcp.server import run_javascript

        with patch("web_mcp.server.get_config", return_value=mock_config):
            result = await run_javascript(
                code="(await fetch('javascript:alert(1)')).text()", timeout_ms=5000, context={}
            )

        assert "Error" in result or "Invalid URL" in result

    @pytest.mark.asyncio
    async def test_allow_public_url(self, mock_config):
        """Test that public URLs are allowed (mocked HTTP call)."""
        from web_mcp.server import run_javascript

        mock_response = create_mock_async_context(
            content=b'{"status":"ok"}',
            status_code=200,
            headers={"content-type": "application/json"},
        )
        mock_client = create_mock_client_with_response(mock_response)

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client):
                    result = await run_javascript(
                        code="(await fetch('https://api.example.com/data')).status",
                        timeout_ms=5000,
                        context={},
                    )

        assert "200" in result

    @pytest.mark.asyncio
    async def test_block_link_local_ip(self, mock_config):
        """Test that link-local IP 169.254.x.x is blocked."""
        from web_mcp.server import run_javascript

        with patch("web_mcp.server.get_config", return_value=mock_config):
            result = await run_javascript(
                code="(await fetch('http://169.254.0.1/metadata')).text()",
                timeout_ms=5000,
                context={},
            )

        assert "Error" in result or "private" in result.lower() or "restricted" in result.lower()

    @pytest.mark.asyncio
    async def test_block_ipv6_loopback(self, mock_config):
        """Test that IPv6 loopback ::1 is blocked."""
        from web_mcp.server import run_javascript

        with patch("web_mcp.server.get_config", return_value=mock_config):
            result = await run_javascript(
                code="(await fetch('http://[::1]/admin')).text()", timeout_ms=5000, context={}
            )

        assert "Error" in result or "private" in result.lower() or "restricted" in result.lower()


class TestJavascriptRateLimiting:
    """Tests for rate limiting in run_javascript fetch."""

    @pytest.mark.asyncio
    async def test_fetch_count_limit(self, mock_config):
        """Test that exceeding max fetch requests is blocked."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_max_requests = 3

        mock_response = create_mock_async_context(content=b"test", status_code=200)
        mock_client = create_mock_client_with_response(mock_response)

        code = """
        const results = [];
        for (let i = 0; i < 5; i++) {
            const resp = await fetch('https://example.com/api/' + i);
            results.push(resp.status);
        }
        return results;
        """

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client):
                    result = await run_javascript(code=code, timeout_ms=5000, context={})

        assert "limit" in result.lower() or "exceeded" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_fetch_count_within_limit(self, mock_config):
        """Test that fetches within limit succeed."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_max_requests = 5

        mock_response = create_mock_async_context(content=b"test", status_code=200)
        mock_client = create_mock_client_with_response(mock_response)

        code = """
        const results = [];
        for (let i = 0; i < 3; i++) {
            const resp = await fetch('https://example.com/api/' + i);
            results.push(resp.status);
        }
        return JSON.stringify(results);
        """

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client):
                    result = await run_javascript(code=code, timeout_ms=5000, context={})

        assert "200" in result

    @pytest.mark.asyncio
    async def test_total_bytes_limit(self, mock_config):
        """Test that exceeding total bytes limit is blocked."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_max_total_bytes = 100
        mock_config.js_fetch_max_response_size = 200

        large_content = b"x" * 80

        mock_response = create_mock_async_context(content=large_content, status_code=200)
        mock_client = create_mock_client_with_response(mock_response)

        code = """
        const results = [];
        for (let i = 0; i < 3; i++) {
            const resp = await fetch('https://example.com/data/' + i);
            results.push(resp.status);
        }
        return results;
        """

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client):
                    result = await run_javascript(code=code, timeout_ms=5000, context={})

        assert (
            "limit" in result.lower()
            or "exceeded" in result.lower()
            or "bytes" in result.lower()
            or "Error" in result
        )


class TestJavascriptResponseSizeLimit:
    """Tests for response size limits in run_javascript fetch."""

    @pytest.mark.asyncio
    async def test_response_exceeds_size_limit_via_content_length(self, mock_config):
        """Test that responses with large content-length are rejected early."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_max_response_size = 100

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {"content-type": "text/plain", "content-length": "1000"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_client = create_mock_client_with_response(mock_response)

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client):
                    result = await run_javascript(
                        code="(await fetch('https://example.com/large')).text()",
                        timeout_ms=5000,
                        context={},
                    )

        assert "too large" in result.lower() or "size" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_response_exceeds_size_limit_during_stream(self, mock_config):
        """Test that responses exceeding max size during streaming are rejected."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_max_response_size = 50

        large_chunk = b"x" * 100

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {"content-type": "text/plain"}

        async def mock_aiter_bytes():
            yield large_chunk

        mock_response.aiter_bytes = mock_aiter_bytes
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_client = create_mock_client_with_response(mock_response)

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client):
                    result = await run_javascript(
                        code="(await fetch('https://example.com/large')).text()",
                        timeout_ms=5000,
                        context={},
                    )

        assert (
            "exceeded" in result.lower()
            or "size" in result.lower()
            or "limit" in result.lower()
            or "Error" in result
        )

    @pytest.mark.asyncio
    async def test_response_within_size_limit(self, mock_config):
        """Test that responses within size limit succeed."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_max_response_size = 1000

        content = b"Hello, World!"

        mock_response = create_mock_async_context(content=content, status_code=200)
        mock_client = create_mock_client_with_response(mock_response)

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client):
                    result = await run_javascript(
                        code="(await fetch('https://example.com/small')).text()",
                        timeout_ms=5000,
                        context={},
                    )

        assert "Hello, World!" in result

    @pytest.mark.asyncio
    async def test_response_with_chunked_encoding(self, mock_config):
        """Test handling of chunked responses without content-length header."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_max_response_size = 1000

        chunks = [b"Hello", b", ", b"World!"]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {"content-type": "text/plain", "transfer-encoding": "chunked"}

        async def mock_aiter_bytes():
            for chunk in chunks:
                yield chunk

        mock_response.aiter_bytes = mock_aiter_bytes
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_client = create_mock_client_with_response(mock_response)

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client):
                    result = await run_javascript(
                        code="(await fetch('https://example.com/chunked')).text()",
                        timeout_ms=5000,
                        context={},
                    )

        assert "Hello, World!" in result


class TestJavascriptSSLVerification:
    """Tests for SSL verification in run_javascript fetch."""

    @pytest.mark.asyncio
    async def test_ssl_verification_default_true(self, mock_config):
        """Test that SSL verification is enabled by default."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_verify_ssl = True

        content = b"Secure response"

        mock_response = create_mock_async_context(content=content, status_code=200)
        mock_client_instance = create_mock_client_with_response(mock_response)

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient") as mock_client_class:
                    mock_client_class.return_value = mock_client_instance
                    result = await run_javascript(
                        code="(await fetch('https://example.com/secure')).text()",
                        timeout_ms=5000,
                        context={},
                    )

                    mock_client_class.assert_called_once()
                    call_kwargs = mock_client_class.call_args[1]
                    assert call_kwargs.get("verify") is True

        assert "Secure response" in result

    @pytest.mark.asyncio
    async def test_ssl_verification_can_be_disabled(self, mock_config):
        """Test that SSL verification can be disabled via config."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_verify_ssl = False

        content = b"Insecure response"

        mock_response = create_mock_async_context(content=content, status_code=200)
        mock_client_instance = create_mock_client_with_response(mock_response)

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient") as mock_client_class:
                    mock_client_class.return_value = mock_client_instance
                    result = await run_javascript(
                        code="(await fetch('https://example.com/insecure')).text()",
                        timeout_ms=5000,
                        context={},
                    )

                    mock_client_class.assert_called_once()
                    call_kwargs = mock_client_class.call_args[1]
                    assert call_kwargs.get("verify") is False

        assert "Insecure response" in result


class TestJavascriptFetchOptions:
    """Tests for fetch options in run_javascript."""

    @pytest.mark.asyncio
    async def test_fetch_with_custom_headers(self, mock_config):
        """Test that custom headers are passed to the request."""
        from web_mcp.server import run_javascript

        mock_response = create_mock_async_context(
            content=b'{"status":"ok"}',
            status_code=200,
            headers={"content-type": "application/json"},
        )
        mock_client_instance = create_mock_client_with_response(mock_response)

        code = """
        const resp = await fetch('https://api.example.com/data', {
            headers: {
                'Authorization': 'Bearer token123',
                'X-Custom-Header': 'custom-value'
            }
        });
        return JSON.stringify(resp.json());
        """

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client_instance):
                    result = await run_javascript(code=code, timeout_ms=5000, context={})

                    call_args = mock_client_instance.stream.call_args
                    assert call_args is not None
                    assert mock_client_instance.stream.call_count == 1

        assert "ok" in result

    @pytest.mark.asyncio
    async def test_fetch_with_post_method(self, mock_config):
        """Test that POST method is passed correctly."""
        from web_mcp.server import run_javascript

        mock_response = create_mock_async_context(
            content=b'{"id":1}',
            status_code=201,
            reason="Created",
            headers={"content-type": "application/json"},
        )
        mock_client_instance = create_mock_client_with_response(mock_response)

        code = """
        const resp = await fetch('https://api.example.com/users', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: 'test'})
        });
        return resp.status;
        """

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client_instance):
                    result = await run_javascript(code=code, timeout_ms=5000, context={})

                    call_args = mock_client_instance.stream.call_args
                    assert call_args[1].get("method") == "POST"
                    assert "name" in call_args[1].get("content", "")

        assert "201" in result

    @pytest.mark.asyncio
    async def test_fetch_response_ok_property(self, mock_config):
        """Test that response.ok is true for 2xx status codes."""
        from web_mcp.server import run_javascript

        mock_response = create_mock_async_context(content=b"", status_code=204, reason="No Content")
        mock_client = create_mock_client_with_response(mock_response)

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client):
                    result = await run_javascript(
                        code="(await fetch('https://example.com/no-content')).ok",
                        timeout_ms=5000,
                        context={},
                    )

        assert "true" in result.lower()

    @pytest.mark.asyncio
    async def test_fetch_response_not_ok_for_4xx(self, mock_config):
        """Test that response.ok is false for 4xx status codes."""
        from web_mcp.server import run_javascript

        mock_response = create_mock_async_context(content=b"", status_code=404, reason="Not Found")
        mock_client = create_mock_client_with_response(mock_response)

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient", return_value=mock_client):
                    result = await run_javascript(
                        code="(await fetch('https://example.com/not-found')).ok",
                        timeout_ms=5000,
                        context={},
                    )

        assert "false" in result.lower()


class TestJavascriptTimeout:
    """Tests for timeout handling in run_javascript."""

    @pytest.mark.asyncio
    async def test_fetch_timeout_from_config(self, mock_config):
        """Test that fetch uses timeout from config."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_timeout = 5000

        mock_response = create_mock_async_context(content=b"ok", status_code=200)
        mock_client_instance = create_mock_client_with_response(mock_response)

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient") as mock_client_class:
                    mock_client_class.return_value = mock_client_instance
                    await run_javascript(
                        code="(await fetch('https://example.com/')).text()",
                        timeout_ms=5000,
                        context={},
                    )

                    call_kwargs = mock_client_class.call_args[1]
                    assert call_kwargs.get("timeout") == 5.0

    @pytest.mark.asyncio
    async def test_fetch_custom_timeout_in_options(self, mock_config):
        """Test that custom timeout in fetch options is used."""
        from web_mcp.server import run_javascript

        mock_config.js_fetch_timeout = 10000

        mock_response = create_mock_async_context(content=b"ok", status_code=200)
        mock_client_instance = create_mock_client_with_response(mock_response)

        code = """
        const resp = await fetch('https://example.com/', {timeout: 2000});
        return resp.text();
        """

        with patch("web_mcp.server.get_config", return_value=mock_config):
            with patch("web_mcp.server.validate_url_ip", return_value=True):
                with patch.object(httpx, "AsyncClient") as mock_client_class:
                    mock_client_class.return_value = mock_client_instance
                    await run_javascript(code=code, timeout_ms=5000, context={})

                    call_kwargs = mock_client_class.call_args[1]
                    assert call_kwargs.get("timeout") == 2.0
