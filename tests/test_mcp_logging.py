"""Unit tests for MCP protocol and lifecycle logging."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_mcp.mcp_logging import (
    REQUEST_ID_CTX,
    _log_msg,
    _make_intercepting_receive,
    _next_seq,
    _parse_message_id,
    _wrap_tool_call,
    get_request_id,
    reset_request_id,
)


class TestParseMessageId:
    """Tests for _parse_message_id function."""

    def test_parse_request_id(self):
        """Test extracting ID from a request message."""
        raw = '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
        assert _parse_message_id(raw) == "1"

    def test_parse_request_id_string(self):
        """Test extracting string ID from a request message."""
        raw = '{"jsonrpc":"2.0","id":"abc-123","method":"tools/call"}'
        assert _parse_message_id(raw) == "abc-123"

    def test_parse_notification(self):
        """Test extracting method from notification (no ID)."""
        raw = '{"jsonrpc":"2.0","method":"notifications/initialized"}'
        assert _parse_message_id(raw) == "notify:notifications/initialized"

    def test_parse_response(self):
        """Test extracting ID from a response message."""
        raw = '{"jsonrpc":"2.0","id":1,"result":{}}'
        assert _parse_message_id(raw) == "1"

    def test_parse_error_response(self):
        """Test extracting ID from an error response."""
        raw = '{"jsonrpc":"2.0","id":5,"error":{"code":-32601,"message":"Not found"}}'
        assert _parse_message_id(raw) == "5"

    def test_parse_invalid_json(self):
        """Test handling invalid JSON."""
        assert _parse_message_id("not json") is None

    def test_parse_empty_object(self):
        """Test handling empty object."""
        assert _parse_message_id("{}") is None

    def test_parse_nil_id(self):
        """Test handling null ID with no method."""
        raw = '{"jsonrpc":"2.0","id":null}'
        assert _parse_message_id(raw) is None


class TestNextSeq:
    """Tests for _next_seq function."""

    def test_next_seq_starts_at_one(self):
        """Test that sequence starts at 1."""
        import web_mcp.mcp_logging as mod

        mod._msg_seq = 0
        assert _next_seq() == 1

    def test_next_seq_increments(self):
        """Test that sequence increments."""
        import web_mcp.mcp_logging as mod

        mod._msg_seq = 0
        assert _next_seq() == 1
        assert _next_seq() == 2
        assert _next_seq() == 3


class TestLogMsg:
    """Tests for _log_msg function."""

    def test_log_msg_debug(self, capsys):
        """Test that log_msg outputs at DEBUG level."""
        import web_mcp.mcp_logging as mod

        mod._msg_seq = 0

        logger = logging.getLogger("web_mcp.protocol")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        try:
            _log_msg("IN", '{"jsonrpc":"2.0","id":1}', 1)
            captured = capsys.readouterr()
            assert "IN" in captured.err
            assert "1:" in captured.err
            assert "jsonrpc" in captured.err
        finally:
            logger.removeHandler(handler)

    def test_log_msg_truncates_long_messages(self, capsys):
        """Test that long messages are truncated."""
        import web_mcp.mcp_logging as mod

        mod._msg_seq = 0

        logger = logging.getLogger("web_mcp.protocol")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        try:
            long_msg = '{"data":"' + "x" * 600 + '"}'
            _log_msg("IN", long_msg, 1)
            captured = capsys.readouterr()
            assert "more chars" in captured.err
        finally:
            logger.removeHandler(handler)


class TestRequestIdContext:
    """Tests for request ID context variable."""

    def test_set_and_get(self):
        """Test setting and getting request ID."""
        REQUEST_ID_CTX.set("test-req-123")
        assert get_request_id() == "test-req-123"

    def test_reset(self):
        """Test resetting request ID."""
        REQUEST_ID_CTX.set("test-req")
        reset_request_id()
        assert get_request_id() is None

    @pytest.mark.asyncio
    async def test_context_isolation(self):
        """Test that context variable is isolated per context."""
        REQUEST_ID_CTX.set("outer")
        assert get_request_id() == "outer"
        REQUEST_ID_CTX.set("inner")
        assert get_request_id() == "inner"
        REQUEST_ID_CTX.set(None)
        assert get_request_id() is None


class TestWrapToolCall:
    """Tests for the _wrap_tool_call function."""

    @pytest.mark.asyncio
    async def test_wrap_tool_call_already_wrapped(self):
        """Test that wrapping twice only wraps once."""
        import web_mcp.mcp_logging as mod

        mod._original_call_tool = None

        mock_mcp = MagicMock()
        mock_original = MagicMock()
        mock_mcp.call_tool = mock_original

        with patch("mcp.server.fastmcp.server.FastMCP", mock_mcp):
            lifecycle_logger = logging.getLogger("test_lifecycle")
            lifecycle_logger.setLevel(logging.INFO)

            _wrap_tool_call(lifecycle_logger)
            first_wrap = mod._original_call_tool

            _wrap_tool_call(lifecycle_logger)

            assert mod._original_call_tool is first_wrap

    @pytest.mark.asyncio
    async def test_wrap_tool_call_patches_fastmcp(self):
        """Test that _wrap_tool_call patches FastMCP.call_tool."""
        import web_mcp.mcp_logging as mod

        mod._original_call_tool = None

        mock_mcp = MagicMock()
        mock_original = MagicMock()
        mock_mcp.call_tool = mock_original

        with patch("mcp.server.fastmcp.server.FastMCP", mock_mcp):
            lifecycle_logger = logging.getLogger("test_lifecycle")
            lifecycle_logger.setLevel(logging.INFO)

            _wrap_tool_call(lifecycle_logger)

            # Verify FastMCP.call_tool was replaced
            assert mock_mcp.call_tool != mock_original
            assert mod._original_call_tool == mock_original


# Note: _logging_stdio_server is tested via integration tests in test_server.py
# The context manager creates background tasks that don't complete in isolation,
# so unit tests for it would require complex stream setup.


class TestIntegration:
    """Integration tests for logging setup."""

    def test_log_msg_does_not_crash_on_invalid_json(self, capsys):
        """Test that _log_msg handles invalid JSON gracefully."""
        import web_mcp.mcp_logging as mod

        mod._msg_seq = 0

        logger = logging.getLogger("web_mcp.protocol")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        try:
            # This should not raise
            _log_msg("IN", "invalid json {{{", 1)
        except Exception as e:
            pytest.fail(f"_log_msg raised unexpected exception: {e}")
        finally:
            logger.removeHandler(handler)


class TestInterceptingReceive:
    """Tests for _make_intercepting_receive ASGI receive interceptor."""

    @pytest.mark.asyncio
    async def test_returns_body_message_unchanged(self, caplog):
        """Test that the interceptor returns the body message so the handler can read it."""
        caplog.set_level(logging.DEBUG)

        mock_receive = AsyncMock()
        mock_receive.return_value = {
            "type": "http.request",
            "body": b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
            "more_body": False,
        }

        protocol_logger = logging.getLogger("web_mcp.protocol")
        lifecycle_logger = logging.getLogger("web_mcp.lifecycle")

        interceptor = _make_intercepting_receive(
            mock_receive, "test-session", "/messages", protocol_logger, lifecycle_logger
        )

        msg = await interceptor()

        assert msg["type"] == "http.request"
        assert msg["body"] == b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
        assert msg["more_body"] is False

    @pytest.mark.asyncio
    async def test_logs_body_once(self, caplog):
        """Test that the body is logged only on the first http.request message."""
        caplog.set_level(logging.DEBUG)

        mock_receive = AsyncMock()
        mock_receive.return_value = {
            "type": "http.request",
            "body": b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
            "more_body": False,
        }

        protocol_logger = logging.getLogger("web_mcp.protocol")
        lifecycle_logger = logging.getLogger("web_mcp.lifecycle")
        protocol_logger.setLevel(logging.DEBUG)
        lifecycle_logger.setLevel(logging.DEBUG)

        interceptor = _make_intercepting_receive(
            mock_receive, "test-session", "/messages", protocol_logger, lifecycle_logger
        )

        # First call — should log and return body
        await interceptor()
        # Second call — should NOT log, just forward
        await interceptor()

        assert len([r for r in caplog.records if "SSE REQUEST" in r.message]) == 1

    @pytest.mark.asyncio
    async def test_forwards_non_body_messages(self):
        """Test that non-body messages are forwarded unchanged."""
        mock_receive = AsyncMock()
        mock_receive.return_value = {"type": "http.disconnect"}

        protocol_logger = logging.getLogger("web_mcp.protocol")
        lifecycle_logger = logging.getLogger("web_mcp.lifecycle")

        interceptor = _make_intercepting_receive(
            mock_receive, "test-session", "/messages", protocol_logger, lifecycle_logger
        )

        msg = await interceptor()
        assert msg == {"type": "http.disconnect"}

    @pytest.mark.asyncio
    async def test_forwards_empty_body_message(self):
        """Test that http.request with empty body is forwarded without logging."""
        mock_receive = AsyncMock()
        mock_receive.return_value = {"type": "http.request", "body": b"", "more_body": False}

        protocol_logger = logging.getLogger("web_mcp.protocol")
        lifecycle_logger = logging.getLogger("web_mcp.lifecycle")

        interceptor = _make_intercepting_receive(
            mock_receive, "test-session", "/messages", protocol_logger, lifecycle_logger
        )

        msg = await interceptor()
        assert msg["body"] == b""

    @pytest.mark.asyncio
    async def test_logs_session_id_and_path(self, caplog):
        """Test that session ID and path are included in lifecycle log."""
        caplog.set_level(logging.INFO)

        mock_receive = AsyncMock()
        mock_receive.return_value = {
            "type": "http.request",
            "body": b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}',
            "more_body": False,
        }

        protocol_logger = logging.getLogger("web_mcp.protocol")
        lifecycle_logger = logging.getLogger("web_mcp.lifecycle")
        lifecycle_logger.setLevel(logging.INFO)

        interceptor = _make_intercepting_receive(
            mock_receive, "abc-123", "/search/messages", protocol_logger, lifecycle_logger
        )

        await interceptor()

        assert any("abc-123" in r.message for r in caplog.records)
        assert any("/search/messages" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_logs_request_id_from_body(self, caplog):
        """Test that the JSON-RPC request ID is extracted and logged."""
        caplog.set_level(logging.DEBUG)

        mock_receive = AsyncMock()
        mock_receive.return_value = {
            "type": "http.request",
            "body": b'{"jsonrpc":"2.0","id":"req-456","method":"tools/call"}',
            "more_body": False,
        }

        protocol_logger = logging.getLogger("web_mcp.protocol")
        lifecycle_logger = logging.getLogger("web_mcp.lifecycle")
        protocol_logger.setLevel(logging.DEBUG)

        interceptor = _make_intercepting_receive(
            mock_receive, "test-session", "/messages", protocol_logger, lifecycle_logger
        )

        await interceptor()

        assert any("req-456" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_multiple_body_chunks(self):
        """Test handling of chunked body (multiple http.request messages)."""
        mock_receive = AsyncMock()
        mock_receive.side_effect = [
            {"type": "http.request", "body": b'{"jsonrpc":"2.0"', "more_body": True},
            {"type": "http.request", "body": b',"id":1,"method":"tools/list"}', "more_body": False},
        ]

        protocol_logger = logging.getLogger("web_mcp.protocol")
        lifecycle_logger = logging.getLogger("web_mcp.lifecycle")

        interceptor = _make_intercepting_receive(
            mock_receive, "test-session", "/messages", protocol_logger, lifecycle_logger
        )

        # First chunk — should log the full assembled body
        msg1 = await interceptor()
        assert msg1["body"] == b'{"jsonrpc":"2.0"'

        # Second chunk — should forward without logging
        msg2 = await interceptor()
        assert msg2["body"] == b',"id":1,"method":"tools/list"}'
