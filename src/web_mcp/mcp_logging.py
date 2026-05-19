"""MCP protocol-level logging for debugging client compatibility issues.

Patches the MCP stdio transport to log all JSON-RPC messages (incoming and outgoing),
adds tool call lifecycle logging, and provides request correlation IDs.

Usage:
    # In server.py, before mcp.run():
    from web_mcp.mcp_logging import setup_mcp_logging
    setup_mcp_logging()

    # Or set WEB_MCP_LOG_LEVEL=DEBUG to enable automatically.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager
from contextvars import ContextVar
from io import TextIOWrapper
from typing import Any

import anyio
import mcp.types as types
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp.shared.message import SessionMessage

# Context variable for correlating requests/responses
REQUEST_ID_CTX: ContextVar[str | None] = ContextVar("request_id", default=None)

# Track active tool calls for correlation
_active_tools: dict[str, str] = {}  # request_id -> tool_name

# Message counters for ordering
_msg_seq = 0


def _next_seq() -> int:
    global _msg_seq
    _msg_seq += 1
    return _msg_seq


def _parse_message_id(raw: str) -> str | None:
    """Extract a stable correlation ID from a JSON-RPC message string."""
    try:
        obj = json.loads(raw)
        rid = obj.get("id")
        if rid is not None:
            return str(rid)
        method = obj.get("method")
        if method:
            return f"notify:{method}"
    except Exception:
        pass
    return None


def _log_msg(direction: str, raw: str, seq: int | None = None) -> None:
    """Log a raw JSON-RPC message with truncation for long bodies."""
    import logging

    logger = logging.getLogger("web_mcp.protocol")
    rid = _parse_message_id(raw)
    seq = seq if seq is not None else _next_seq()

    # Truncate payload for logging (keep first 500 chars)
    payload = raw[:500]
    if len(raw) > 500:
        payload += f"... ({len(raw) - 500} more chars)"

    logger.debug(f"[seq:{seq}] {direction} {rid}: {payload}")


@asynccontextmanager
async def _logging_stdio_server(
    stdin: anyio.AsyncFile[str] | None = None,
    stdout: anyio.AsyncFile[str] | None = None,
):
    """Wrapper around stdio_server that logs all JSON-RPC messages."""
    import logging

    logger = logging.getLogger("web_mcp.protocol")
    logger.info("MCP stdio transport: reading from stdin, writing to stdout")

    # Purposely not using context managers for these, as we don't want to close
    # standard process handles.
    if not stdin:
        stdin = anyio.wrap_file(TextIOWrapper(sys.stdin.buffer, encoding="utf-8"))
    if not stdout:
        stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))

    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]

    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    async def stdin_reader():
        import logging as _logging

        _logger = _logging.getLogger("web_mcp.protocol")
        seq = 0
        try:
            async with read_stream_writer:
                async for line in stdin:
                    if not line:
                        continue
                    seq += 1
                    _log_msg("<- IN", line, seq)

                    try:
                        message = types.JSONRPCMessage.model_validate_json(line)
                    except Exception as exc:
                        _logger.warning(f"[seq:{seq}] Failed to parse JSON-RPC message: {exc}")
                        await read_stream_writer.send(exc)
                        continue

                    # Track request ID for correlation
                    msg_id = _parse_message_id(line)
                    if msg_id:
                        REQUEST_ID_CTX.set(msg_id)

                    session_message = SessionMessage(message)
                    await read_stream_writer.send(session_message)
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()

    async def stdout_writer():
        import logging as _logging

        _logger = _logging.getLogger("web_mcp.protocol")
        seq = 0
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    seq += 1
                    json_str = session_message.message.model_dump_json(
                        by_alias=True, exclude_none=True
                    )
                    _log_msg("-> OUT", json_str, seq)
                    if stdout is not None:
                        await stdout.write(json_str + "\n")
                        await stdout.flush()
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()

    async with anyio.create_task_group() as tg:
        tg.start_soon(stdin_reader)
        tg.start_soon(stdout_writer)
        yield read_stream, write_stream


# ---------------------------------------------------------------------------
# Tool call lifecycle logging
# ---------------------------------------------------------------------------

# Store original call_tool for patching
_original_call_tool: Any = None


def _wrap_tool_call(lifecycle_logger: logging.Logger) -> None:
    """Patch FastMCP's call_tool to add lifecycle logging."""
    from mcp.server.fastmcp.server import FastMCP

    global _original_call_tool

    if _original_call_tool is not None:
        return  # Already wrapped

    original = FastMCP.call_tool

    async def wrapped_call_tool(self, name: str, arguments: dict[str, Any]):
        req_id = REQUEST_ID_CTX.get() or "no-id"
        lifecycle_logger.info(
            f"[{req_id}] TOOL CALL START: {name}(args={json.dumps(arguments, default=str)[:300]})"
        )
        start_time = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0

        try:
            result = await original(self, name, arguments)
            elapsed = 0
            if start_time:
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            result_preview = str(result)[:500]
            lifecycle_logger.info(
                f"[{req_id}] TOOL CALL OK: {name} completed in {elapsed:.0f}ms, "
                f"result={json.dumps(result_preview, default=str)[:300]}"
            )
            return result
        except Exception as e:
            elapsed = 0
            if start_time:
                elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            lifecycle_logger.error(
                f"[{req_id}] TOOL CALL FAIL: {name} after {elapsed:.0f}ms: {type(e).__name__}: {e}",
                exc_info=True,
            )
            raise

    FastMCP.call_tool = wrapped_call_tool
    _original_call_tool = original


# ---------------------------------------------------------------------------
# Initialization logging
# ---------------------------------------------------------------------------

_original_mcp_run: Any = None


def _wrap_mcp_run(lifecycle_logger: logging.Logger) -> None:
    """Patch MCPServer.run to log initialization and protocol events."""
    from mcp.server.lowlevel.server import Server as MCPServer

    global _original_mcp_run

    if _original_mcp_run is not None:
        return

    original = MCPServer.run

    async def wrapped_run(self, read_stream, write_stream, init_options):
        lifecycle_logger.info(
            f"MCP server '{init_options.server_name}/{init_options.server_version}' "
            f"starting with {len(init_options.capabilities.__dict__)} capability groups"
        )
        lifecycle_logger.debug(f"Server capabilities: {init_options.capabilities}")
        try:
            await original(self, read_stream, write_stream, init_options)
        except Exception as e:
            lifecycle_logger.error(f"MCP server run loop exited with error: {e}", exc_info=True)
            raise

    MCPServer.run = wrapped_run
    _original_mcp_run = original


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _wrap_sse_transport(lifecycle_logger: logging.Logger, protocol_logger: logging.Logger) -> None:
    """Patch SseServerTransport to log HTTP-level JSON-RPC messages."""
    try:
        from mcp.server.sse import SseServerTransport
    except ImportError:
        return

    original_handle_post = SseServerTransport.handle_post_message

    async def wrapped_handle_post_message(self, scope: Any, receive: Any, send: Any) -> None:
        from starlette.requests import Request

        request = Request(scope, receive)
        body = await request.body()

        session_id_param = request.query_params.get("session_id", "unknown")
        rid = _parse_message_id(body.decode("utf-8", errors="replace"))
        seq = _next_seq()

        payload = body.decode("utf-8", errors="replace")[:500]
        if len(body) > 500:
            payload += f" ... ({len(body) - 500} more bytes)"

        protocol_logger.debug(f"[seq:{seq}] SSE POST [{session_id_param}] {rid}: {payload}")

        lifecycle_logger.info(
            f"[{rid or session_id_param}] SSE REQUEST: POST {request.url.path} "
            f"session={session_id_param} content-length={len(body)}"
        )

        # Cache body and intercept receive so the original handler can read it again
        _cached_body: bytearray = bytearray(body)
        _body_consumed = False

        async def caching_receive() -> dict[str, Any]:
            nonlocal _body_consumed
            if not _body_consumed:
                _body_consumed = True
                return {"type": "http.request", "body": bytes(_cached_body), "more_body": False}
            return await receive()

        await original_handle_post(self, scope, caching_receive, send)

    SseServerTransport.handle_post_message = wrapped_handle_post_message  # type: ignore[assignment]

    lifecycle_logger.info("MCP SSE transport: HTTP-level logging enabled")


def setup_mcp_logging() -> None:
    """Set up comprehensive MCP protocol logging.

    This patches the MCP stdio transport to log all JSON-RPC messages,
    adds tool call lifecycle logging, and patches the MCP server run loop.

    Call this BEFORE mcp.run() in your server entry point.
    """
    import logging

    # Configure the protocol logger
    protocol_logger = logging.getLogger("web_mcp.protocol")
    protocol_logger.setLevel(logging.DEBUG)

    # Configure the lifecycle logger
    lifecycle_logger = logging.getLogger("web_mcp.lifecycle")
    lifecycle_logger.setLevel(logging.DEBUG)

    # Root logger gets INFO by default, DEBUG if WEB_MCP_LOG_LEVEL=DEBUG
    root_level = logging.getLogger().level
    if root_level <= logging.DEBUG:
        protocol_logger.setLevel(logging.DEBUG)
        lifecycle_logger.setLevel(logging.DEBUG)
    else:
        # Even at INFO, log tool calls (use INFO level for lifecycle)
        lifecycle_logger.setLevel(logging.INFO)
        protocol_logger.setLevel(logging.WARNING)

    # Add handlers if none exist (inherit from root)
    if not protocol_logger.handlers:
        protocol_logger.propagate = True
    if not lifecycle_logger.handlers:
        lifecycle_logger.propagate = True

    # Patch the stdio transport
    import mcp.server.fastmcp.server as fastmcp_server_mod

    fastmcp_server_mod.stdio_server = _logging_stdio_server  # type: ignore[assignment]

    # Also patch at the module level where it's imported

    # Patch SSE transport for HTTP/SSE mode
    _wrap_sse_transport(lifecycle_logger, protocol_logger)

    # Patch tool call lifecycle
    _wrap_tool_call(lifecycle_logger)

    # Patch MCP server run loop
    _wrap_mcp_run(lifecycle_logger)

    lifecycle_logger.info("MCP protocol logging enabled")
    lifecycle_logger.info("Set WEB_MCP_LOG_LEVEL=DEBUG for full JSON-RPC message tracing")


def get_request_id() -> str | None:
    """Get the current request correlation ID."""
    return REQUEST_ID_CTX.get()


def reset_request_id() -> None:
    """Reset the current request correlation ID."""
    REQUEST_ID_CTX.set(None)
