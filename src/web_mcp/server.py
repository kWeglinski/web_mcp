"""Web Browsing MCP Server - Browse the web with context-aware content extraction."""

import json
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

# Add src to path for absolute imports when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import UTC

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl, Field

from web_mcp.charts import ChartConfig, ChartError, create_chart
from web_mcp.config import get_config
from web_mcp.content_store import get_content_store, start_cleanup_task, stop_cleanup_task
from web_mcp.extractors.custom import CustomSelectorExtractor
from web_mcp.extractors.trafilatura import TrafilaturaExtractor
from web_mcp.fetcher import FetchError, fetch_url_with_fallback
from web_mcp.logging import get_logger, setup_logging
from web_mcp.playwright_fetcher import PlaywrightFetchError
from web_mcp.searxng import search
from web_mcp.security import validate_url, validate_url_ip


class StaticTokenVerifier:
    """Simple token verifier that validates against a static token."""

    def __init__(self, expected_token: str):
        self.expected_token = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        if token == self.expected_token:
            return AccessToken(token=token, client_id="static", scopes=[])
        return None


def create_auth_config() -> tuple[TokenVerifier | None, AuthSettings | None]:
    """Create auth configuration if WEB_MCP_AUTH_TOKEN is set."""
    auth_token = os.environ.get("WEB_MCP_AUTH_TOKEN")
    if auth_token:
        server_url = f"http://{SERVER_HOST}:{SERVER_PORT}"
        return (
            StaticTokenVerifier(auth_token),
            AuthSettings(
                issuer_url=AnyHttpUrl(server_url),
                resource_server_url=AnyHttpUrl(server_url),
            ),
        )
    return None, None


# Server configuration
SERVER_HOST = os.environ.get("WEB_MCP_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("WEB_MCP_SERVER_PORT", "8000"))
VERSION = "1.0.0"

# Output schemas disabled by default to reduce context footprint
# Set WEB_MCP_OUTPUT_SCHEMAS=true to enable
OUTPUT_SCHEMAS = os.environ.get("WEB_MCP_OUTPUT_SCHEMAS", "").lower() in ("true", "1", "yes")

# Setup logging
setup_logging()

logger = get_logger(__name__)

# Server start time for uptime calculation
SERVER_START_TIME: float = time.time()

# Global metrics
_request_count: int = 0
_cache_hits: int = 0


def increment_request_count() -> None:
    """Increment the request count."""
    global _request_count
    _request_count += 1


def increment_cache_hits() -> None:
    """Increment the cache hits counter."""
    global _cache_hits
    _cache_hits += 1


def get_health_metrics() -> dict:
    """Get health metrics for the /health endpoint.

    Returns:
        Dictionary with health metrics
    """
    global _request_count, _cache_hits
    uptime = time.time() - SERVER_START_TIME

    # Calculate cache hit rate
    total_requests = _request_count + _cache_hits
    cache_hit_rate = (_cache_hits / total_requests) if total_requests > 0 else 0.0

    return {
        "status": "healthy",
        "version": VERSION,
        "cache_hit_rate": round(cache_hit_rate, 4),
        "request_count": _request_count,
        "uptime_seconds": round(uptime, 2),
    }


@asynccontextmanager
async def lifespan(app):
    start_cleanup_task()
    try:
        yield
    finally:
        stop_cleanup_task()


# Create MCP server with SSE transport support
_token_verifier, _auth_settings = create_auth_config()
if _token_verifier:
    logger.info("Authentication enabled: Bearer token required for MCP endpoints")
mcp = FastMCP(
    name="web-browsing",
    instructions="A web browsing MCP server that extracts content from URLs with context optimization. "
    "Use `get_page` to browse websites and extract their main content, "
    "`search_web` to search the web using SearXNG.",
    host=SERVER_HOST,
    port=SERVER_PORT,
    lifespan=lifespan,
    token_verifier=_token_verifier,
    auth=_auth_settings,
)


@mcp.custom_route("/c/{content_id}", methods=["GET"])
async def serve_stored_content(request):
    from starlette.responses import HTMLResponse, PlainTextResponse, Response

    content_id = request.path_params.get("content_id", "")
    if not content_id or not all(c.isalnum() for c in content_id):
        return Response(content="Invalid content ID", status_code=400)

    store = get_content_store()
    stored = store.get(content_id)

    if stored is None:
        return Response(content="Content not found or expired", status_code=404)

    token = request.query_params.get("token", "")
    if token != stored.token:
        return Response(content="Unauthorized", status_code=401)

    content_type = stored.content_type
    content = stored.content
    if isinstance(content, bytes):
        return Response(content=content, media_type=content_type)
    elif content_type.startswith("text/html"):
        return HTMLResponse(content=content)
    elif content_type.startswith("text/"):
        return PlainTextResponse(content=content, media_type=content_type)
    else:
        return Response(content=content, media_type=content_type)


@mcp.custom_route("/i/{content_id}", methods=["GET"])
async def serve_chart_image(request):
    from starlette.responses import Response

    content_id = request.path_params.get("content_id", "")
    if content_id.endswith(".png"):
        content_id = content_id[:-4]

    if not content_id or not all(c.isalnum() for c in content_id):
        return Response(content="Invalid content ID", status_code=400)

    store = get_content_store()
    stored = store.get(content_id)

    if stored is None:
        return Response(content="Image not found or expired", status_code=404)

    token = request.query_params.get("token", "")
    if token != stored.token:
        return Response(content="Unauthorized", status_code=401)

    content = stored.content
    if isinstance(content, bytes):
        return Response(
            content=content,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    else:
        return Response(content="Invalid image data", status_code=500)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True), structured_output=OUTPUT_SCHEMAS)
async def render_html(
    html: str = Field(description="HTML content to render"),
    content_type: str = Field(default="text/html", description="MIME type"),
) -> str:
    """Store HTML content and return a viewable URL. Requires WEB_MCP_PUBLIC_URL. Content expires after 1 hour."""
    increment_request_count()

    config = get_config()

    if not config.public_url:
        return "Error: WEB_MCP_PUBLIC_URL not configured. Set it to your server's public URL (e.g., https://mcp.example.com)"

    store = get_content_store()
    content_id, token = store.store(html, content_type=content_type)

    url = f"{config.public_url}/c/{content_id}?token={token}"

    return url


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True), structured_output=OUTPUT_SCHEMAS)
async def health() -> dict[str, Any]:
    """Get server health metrics: cache hit rate, request count, uptime."""
    increment_request_count()
    logger.info("Health check requested")
    return get_health_metrics()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True), structured_output=OUTPUT_SCHEMAS)
async def current_datetime(
    timezone: str = Field(default="UTC", description="Timezone (e.g., UTC, America/New_York)"),
    format: str = Field(default="iso", description="Format: iso, unix, or readable"),
) -> str:
    """Get current date/time in specified timezone. Formats: iso, unix, readable."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    increment_request_count()

    try:
        if timezone.upper() == "UTC":
            now = datetime.now(UTC)
        else:
            tz_info = ZoneInfo(timezone)
            now = datetime.now(tz_info)

        if format == "unix":
            return str(int(now.timestamp()))
        elif format == "readable":
            return now.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z")
        else:
            return now.isoformat()
    except Exception as e:
        return f"Error: {e}"


# Default extractor
_default_extractor = TrafilaturaExtractor()
_custom_extractor = CustomSelectorExtractor()


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    structured_output=OUTPUT_SCHEMAS,
)
async def get_page(
    url: str = Field(description="URL to fetch"),
    query: str | None = Field(
        default=None, description="Return only BM25-relevant chunks for this query"
    ),
    extractor: str = Field(
        default="trafilatura", description="Extractor: trafilatura, readability, or custom"
    ),
) -> str:
    """Fetch and extract main content from a URL. Use query for BM25-ranked chunk retrieval."""
    config = get_config()

    try:
        html = await fetch_url_with_fallback(url, config)
    except (FetchError, PlaywrightFetchError) as e:
        return f"Error fetching URL: {e}"

    if query:
        from web_mcp.research.bm25 import BM25
        from web_mcp.research.chunker import chunk_text

        try:
            extracted = await _default_extractor.extract(html, url)
        except Exception as e:
            return f"Error extracting content: {e}"

        if not extracted.text or not extracted.text.strip():
            return "No content extracted from page"

        chunks = chunk_text(
            extracted.text,
            url,
            extracted.title or url,
            chunk_size=500,
            overlap=50,
        )

        if not chunks:
            return extracted.text[:2000] if extracted.text else "No content"

        documents = [{"text": c.text, "chunk": c} for c in chunks]
        bm25 = BM25()
        bm25.fit(documents, text_field="text")
        ranked = bm25.rank(query)

        top_chunks = ranked[:5]

        header = f"Title: {extracted.title}\n\n" if extracted.title else ""

        parts = []
        for doc, _score in top_chunks:
            chunk = doc["chunk"]
            parts.append(chunk.text)

        return header + "\n\n---\n\n".join(parts)

    if extractor == "readability":
        from web_mcp.extractors.readability import ReadabilityExtractor

        extractor_obj = ReadabilityExtractor()
    elif extractor == "custom":
        extractor_obj = _custom_extractor
    else:
        extractor_obj = _default_extractor

    try:
        extracted = await extractor_obj.extract(html, url)
    except Exception as e:
        return f"Error extracting content: {e}"

    return extracted.text


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
    structured_output=OUTPUT_SCHEMAS,
)
async def search_web(
    query: str = Field(description="Search query"),
) -> str:
    """Search the web via SearXNG. Returns top 5 results ranked by BM25 relevance."""
    from web_mcp.searxng import parse_searxng_to_markdown

    try:
        results = await search(query, 30)

        if results:
            from web_mcp.research.bm25 import rerank_search_results

            results = rerank_search_results(results, query)

        json_data = {"results": results}
        return parse_searxng_to_markdown(json_data, query, max_results=5)

    except Exception as e:
        return f"*Search failed: {e}*"


@mcp.tool(annotations=ToolAnnotations(openWorldHint=True), structured_output=OUTPUT_SCHEMAS)
async def create_chart_tool(
    type: str = Field(
        description="Chart type: line, bar, scatter, pie, area, histogram, box, heatmap, treemap, sunburst, funnel, gauge, indicator, bubble"
    ),
    data: dict = Field(description="Chart data (keys: x, y, values, labels, names, etc.)"),
    title: str = Field(default="", description="Chart title"),
    x_label: str = Field(default="", description="X-axis label"),
    y_label: str = Field(default="", description="Y-axis label"),
    options: dict = Field(
        default_factory=dict, description="Styling: width, height, template, colors"
    ),
    output: str = Field(default="html", description="Output: html, url, or image"),
) -> str:
    """Create interactive Plotly chart. Output as HTML, URL (requires WEB_MCP_PUBLIC_URL), or PNG image."""
    increment_request_count()

    valid_types = [
        "line",
        "bar",
        "scatter",
        "pie",
        "area",
        "histogram",
        "box",
        "heatmap",
        "treemap",
        "sunburst",
        "funnel",
        "gauge",
        "indicator",
        "bubble",
    ]
    if type not in valid_types:
        return f"Error: Invalid chart type '{type}'. Valid types: {', '.join(valid_types)}"

    valid_outputs = ["html", "url", "image"]
    if output not in valid_outputs:
        return f"Error: Invalid output format '{output}'. Valid formats: {', '.join(valid_outputs)}"

    config = get_config()

    if output == "url" and not config.public_url:
        return "Error: WEB_MCP_PUBLIC_URL not configured. Set it to your server's public URL for URL output."

    if output == "image" and not config.public_url:
        return "Error: WEB_MCP_PUBLIC_URL not configured. Set it to your server's public URL for image output."

    try:
        from web_mcp.charts.generator import CHART_TYPES, create_chart_image_bytes

        chart_type: CHART_TYPES = type  # type: ignore
        chart_config = ChartConfig(
            type=chart_type,
            title=title,
            x_label=x_label,
            y_label=y_label,
            data=data,
            options=options,
        )

        if output == "image":
            img_bytes = create_chart_image_bytes(chart_config)
            store = get_content_store()
            content_id, token = store.store(img_bytes, content_type="image/png")
            url = f"{config.public_url}/i/{content_id}.png?token={token}"
            return f"{url}\n\nEmbed in markdown: ![chart]({url})"
        elif output == "url":
            html = create_chart(chart_config)
            store = get_content_store()
            content_id, token = store.store(html, content_type="text/html")
            url = f"{config.public_url}/c/{content_id}?token={token}"
            return url
        else:
            html = create_chart(chart_config)
            return html
    except ChartError as e:
        return f"Error creating chart: {e}"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(destructiveHint=True, openWorldHint=True),
    structured_output=OUTPUT_SCHEMAS,
)
async def run_javascript(
    code: str = Field(description="JavaScript code to execute"),
    timeout_ms: int = Field(default=5000, description="Timeout in ms"),
    context: dict = Field(default_factory=dict, description="Variables to inject into JS context"),
) -> str:
    """Execute JavaScript in sandboxed V8. Supports async/await and fetch(). Has SSRF protection."""
    import asyncio

    import httpx

    config = get_config()
    increment_request_count()

    code = code.strip()
    if (code.startswith('"') and code.endswith('"')) or (
        code.startswith("'") and code.endswith("'")
    ):
        code = code[1:-1]

    try:
        from py_mini_racer import MiniRacer
    except ImportError:
        return "Error: mini-racer not installed. Run: pip install mini-racer"

    fetch_state = {"fetch_count": 0, "total_bytes": 0}

    async def py_fetch(url: str, options: dict = None) -> str:
        """HTTP fetch implementation with security controls - returns JSON string."""
        options = options or {}

        if not validate_url(url):
            return json.dumps({"error": "Invalid URL: must use http or https scheme", "status": 0})
        if not validate_url_ip(url):
            return json.dumps(
                {"error": "URL resolves to private/restricted IP address", "status": 0}
            )

        if fetch_state["fetch_count"] >= config.js_fetch_max_requests:
            return json.dumps(
                {
                    "error": f"Fetch limit exceeded (max {config.js_fetch_max_requests} requests)",
                    "status": 0,
                }
            )

        method = options.get("method", "GET")
        headers = options.get("headers", {})
        body = options.get("body")
        timeout = options.get("timeout", config.js_fetch_timeout) / 1000.0

        try:
            verify_ssl = config.js_fetch_verify_ssl

            async with httpx.AsyncClient(timeout=timeout, verify=verify_ssl) as client:
                async with client.stream(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body,
                    follow_redirects=True,
                ) as response:
                    content_length = response.headers.get("content-length")
                    if content_length:
                        size = int(content_length)
                        if size > config.js_fetch_max_response_size:
                            return json.dumps(
                                {
                                    "error": f"Response too large: {size} bytes (max {config.js_fetch_max_response_size})",
                                    "status": 0,
                                }
                            )
                        if fetch_state["total_bytes"] + size > config.js_fetch_max_total_bytes:
                            return json.dumps(
                                {
                                    "error": f"Total fetch limit exceeded (max {config.js_fetch_max_total_bytes} bytes)",
                                    "status": 0,
                                }
                            )

                    body_bytes = b""
                    async for chunk in response.aiter_bytes():
                        body_bytes += chunk
                        if len(body_bytes) > config.js_fetch_max_response_size:
                            return json.dumps(
                                {
                                    "error": f"Response exceeded size limit ({config.js_fetch_max_response_size} bytes)",
                                    "status": 0,
                                }
                            )
                        if (
                            fetch_state["total_bytes"] + len(body_bytes)
                            > config.js_fetch_max_total_bytes
                        ):
                            return json.dumps(
                                {
                                    "error": f"Total fetch limit exceeded (max {config.js_fetch_max_total_bytes} bytes)",
                                    "status": 0,
                                }
                            )

                    fetch_state["fetch_count"] += 1
                    fetch_state["total_bytes"] += len(body_bytes)

                    result = {
                        "status": response.status_code,
                        "statusText": response.reason_phrase,
                        "headers": dict(response.headers),
                        "body": body_bytes.decode("utf-8", errors="replace"),
                    }
                    return json.dumps(result)

        except httpx.TimeoutException:
            return json.dumps({"error": f"Request timed out after {timeout}s", "status": 0})
        except Exception as e:
            return json.dumps({"error": str(e), "status": 0})

    try:
        mr = MiniRacer()

        context_lines = []
        for key, value in context.items():
            if not key.isidentifier():
                return (
                    f"Error: Invalid context variable name '{key}'. Must be a valid JS identifier."
                )
            context_lines.append(f"const {key} = {json.dumps(value)};")

        context_code = "\n".join(context_lines)

        code_trimmed = code.strip()
        is_statement = code_trimmed.endswith((";", "}"))

        if is_statement:
            full_code = f"(async () => {{\n{context_code}\n{code_trimmed}\n}})()"
        else:
            if context_code:
                full_code = f"(async () => {{\n{context_code}\nreturn JSON.stringify({code_trimmed});\n}})()"
            else:
                full_code = f"(async () => {{ return JSON.stringify({code_trimmed}); }})()"

        effective_timeout_ms = min(timeout_ms, config.js_execution_timeout)
        timeout_sec = effective_timeout_ms / 1000.0

        async with mr._ctx.wrap_py_function_as_js_function(py_fetch) as js_fetch:
            global_obj = await mr._ctx.eval_cancelable("globalThis")
            global_obj["__fetch_raw"] = js_fetch

            await mr._ctx.eval_cancelable("""
                class Response {
                    constructor(data) {
                        this._body = data.body || '';
                        this.status = data.status || 0;
                        this.statusText = data.statusText || '';
                        this.headers = data.headers || {};
                        this.ok = this.status >= 200 && this.status < 300;
                    }

                    json() {
                        return JSON.parse(this._body);
                    }

                    text() {
                        return this._body;
                    }

                    get body() {
                        return this._body;
                    }
                }

                async function fetch(url, options) {
                    const s = await __fetch_raw(url, options || {});
                    const data = JSON.parse(s);
                    if (data.error) {
                        throw new Error(data.error);
                    }
                    return new Response(data);
                }
            """)

            try:
                result = await asyncio.wait_for(mr.eval_cancelable(full_code), timeout=timeout_sec)
            except TimeoutError:
                return f"Error: Execution timed out after {effective_timeout_ms}ms"

            if hasattr(result, "__class__") and "Promise" in result.__class__.__name__:
                try:
                    result = await asyncio.wait_for(
                        mr._ctx.await_promise(result), timeout=timeout_sec
                    )
                except TimeoutError:
                    return f"Error: Execution timed out after {effective_timeout_ms}ms"

        if result is None:
            return "null"

        if isinstance(result, str):
            try:
                parsed = json.loads(result)
                return json.dumps(parsed, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                return result

        if isinstance(result, (int, float, bool)):
            return json.dumps(result)

        return str(result)

    except Exception as e:
        error_msg = str(e)
        return f"Error: {error_msg}"


def main():
    """Run the MCP server."""
    import sys

    tools = "get_page, search_web, create_chart_tool, render_html, current_datetime, health, run_javascript"

    if "--http" in sys.argv or "--streamable-http" in sys.argv:
        logger.info(f"Starting MCP server on http://{SERVER_HOST}:{SERVER_PORT}")
        logger.info(f"Tools available: {tools}")
        mcp.run(transport="streamable-http", mount_path="/mcp")
    elif "--sse" in sys.argv:
        logger.info(f"Starting MCP server on http://{SERVER_HOST}:{SERVER_PORT}")
        logger.info(f"Tools available: {tools}")
        mcp.run(transport="sse", mount_path="/sse")
    else:
        logger.info("Starting MCP server in stdio mode")
        mcp.run()


if __name__ == "__main__":
    main()
