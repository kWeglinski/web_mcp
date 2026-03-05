"""Web Browsing MCP Server - Browse the web with context-aware content extraction."""

import json
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Optional

# Add src to path for absolute imports when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from pydantic import BaseModel, Field, AnyHttpUrl

from web_mcp.config import Config, get_config
from web_mcp.fetcher import FetchError, fetch_url_with_fallback, fetch_url as fetch_html_httpx
from web_mcp.playwright_fetcher import fetch_with_playwright_cached, PlaywrightFetchError
from web_mcp.extractors.trafilatura import TrafilaturaExtractor
from web_mcp.extractors.custom import CustomSelectorExtractor
from web_mcp.optimizer import optimize_content, estimate_tokens
from web_mcp.searxng import search
from web_mcp.logging import setup_logging, get_logger
from web_mcp.charts import create_chart, ChartConfig, ChartError
from web_mcp.content_store import get_content_store, start_cleanup_task, stop_cleanup_task


class StaticTokenVerifier:
    """Simple token verifier that validates against a static token."""
    
    def __init__(self, expected_token: str):
        self.expected_token = expected_token
    
    async def verify_token(self, token: str) -> AccessToken | None:
        if token == self.expected_token:
            return AccessToken(
                token=token,
                client_id="static",
                scopes=[]
            )
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
            )
        )
    return None, None

# Server configuration
SERVER_HOST = os.environ.get("WEB_MCP_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("WEB_MCP_SERVER_PORT", "8000"))
VERSION = "1.0.0"

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
    from starlette.responses import Response, HTMLResponse, PlainTextResponse
    
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
        return Response(content=content, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
    else:
        return Response(content="Invalid image data", status_code=500)


@mcp.tool()
async def render_html(
    html: str = Field(description="HTML/CSS/JS content to render"),
    content_type: str = Field(
        default="text/html",
        description="Content MIME type (text/html, text/css, application/javascript)"
    ),
) -> str:
    """Store HTML/CSS/JS content and return a viewable URL.
    
    Content is stored for 1 hour (configurable via WEB_MCP_CONTENT_TTL) with a unique URL.
    Requires WEB_MCP_PUBLIC_URL to be configured for URL output.
    
    Args:
        html: HTML content to render (can include CSS in <style> and JS in <script> tags)
        content_type: MIME type of the content (default: text/html)
        
    Returns:
        Full URL to view the content, or error message if WEB_MCP_PUBLIC_URL not configured
    """
    increment_request_count()
    
    config = get_config()
    
    if not config.public_url:
        return "Error: WEB_MCP_PUBLIC_URL not configured. Set it to your server's public URL (e.g., https://mcp.example.com)"
    
    store = get_content_store()
    content_id, token = store.store(html, content_type=content_type)
    
    url = f"{config.public_url}/c/{content_id}?token={token}"
    
    return url


@mcp.tool()
async def health() -> dict:
    """Get server health metrics.
    
    Returns:
        Dictionary with health metrics including cache hit rate, request count, and uptime
    """
    increment_request_count()
    logger.info("Health check requested")
    return get_health_metrics()


@mcp.tool()
async def current_datetime(
    timezone: str = Field(
        default="UTC",
        description="Timezone name (e.g., 'UTC', 'America/New_York', 'Europe/London')"
    ),
    format: str = Field(
        default="iso",
        description="Output format: 'iso' (ISO 8601), 'unix' (timestamp), or 'readable' (human-readable)"
    )
) -> str:
    """Get the current date and time.
    
    Returns the current date and time in the specified timezone and format.
    
    Args:
        timezone: Timezone name (default: UTC)
        format: Output format - 'iso', 'unix', or 'readable'
        
    Returns:
        Current date and time as a string
    """
    from datetime import datetime, timezone as tz
    from zoneinfo import ZoneInfo
    
    increment_request_count()
    
    try:
        if timezone.upper() == "UTC":
            now = datetime.now(tz.utc)
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


@mcp.tool()
async def get_page(
    url: str = Field(description="The URL to fetch"),
    query: Optional[str] = Field(
        default=None,
        description="If provided, returns only chunks relevant to this query using BM25 ranking"
    ),
    extractor: str = Field(
        default="trafilatura",
        description="Extractor to use: 'trafilatura', 'readability', or 'custom'"
    )
) -> str:
    """Fetch and extract content from a URL.
    
    Args:
        url: The URL to fetch
        query: If provided, returns only relevant chunks using BM25 ranking
        extractor: Which extractor to use
        
    Returns:
        Extracted text content
    """
    config = get_config()
    
    try:
        html = await fetch_url_with_fallback(url, config)
    except (FetchError, PlaywrightFetchError) as e:
        return f"Error fetching URL: {e}"
    
    if query:
        from web_mcp.research.chunker import chunk_text
        from web_mcp.research.bm25 import BM25
        
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
        
        if extracted.title:
            header = f"Title: {extracted.title}\n\n"
        else:
            header = ""
        
        parts = []
        for doc, score in top_chunks:
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


@mcp.tool()
async def search_web(
    query: str = Field(description="The search query string")
) -> str:
    """Search the web using SearXNG and return results as LLM-optimized markdown.
    
    Fetches 30 results, reranks by relevance using BM25, and returns top 5
    formatted as markdown for optimal LLM context window usage.
    
    Args:
        query: The search query string
        
    Returns:
        Markdown-formatted search results
    """
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


@mcp.tool()
async def create_chart_tool(
    type: str = Field(
        description="Chart type: line, bar, scatter, pie, area, histogram, box, heatmap, treemap, sunburst, funnel, gauge, indicator, bubble"
    ),
    data: dict = Field(
        description="Chart data as JSON. Keys vary by chart type. Common: x, y, values, labels, names"
    ),
    title: str = Field(
        default="",
        description="Chart title"
    ),
    x_label: str = Field(
        default="",
        description="X-axis label"
    ),
    y_label: str = Field(
        default="",
        description="Y-axis label"
    ),
    options: dict = Field(
        default_factory=dict,
        description="Additional options: width, height, template, show_legend, colors"
    ),
    output: str = Field(
        default="html",
        description="Output format: 'html' (raw HTML), 'url' (viewable link), 'image' (PNG URL)"
    ),
) -> str:
    """Create an interactive Plotly chart.
    
    Creates 14 chart types with modern, interactive visualizations.
    
    Output formats:
    - html: Returns full HTML with embedded Plotly (default)
    - url: Stores chart and returns viewable URL (requires WEB_MCP_PUBLIC_URL)
    - image: Stores PNG and returns viewable image URL (requires WEB_MCP_PUBLIC_URL)
    
    Chart types and required data keys:
    - line, bar, scatter, area: x (labels), y (values)
    - pie: labels, values
    - histogram: x (values to bin)
    - box: y (values), optional x (groups)
    - heatmap: z (2D matrix), optional x, y (labels)
    - treemap, sunburst: labels, values, parents
    - funnel: labels (stages), values
    - gauge: value, optional min, max, threshold
    - indicator: value, optional delta (reference value)
    - bubble: x, y, size, optional color
    
    Args:
        type: Chart type (line, bar, scatter, pie, area, histogram, box, heatmap, treemap, sunburst, funnel, gauge, indicator, bubble)
        data: Chart data as JSON object with keys appropriate for chart type
        title: Chart title
        x_label: X-axis label
        y_label: Y-axis label
        options: Additional styling options (width, height, template, show_legend, colors)
        output: Output format - 'html', 'url', or 'image'
        
    Returns:
        HTML string, URL, or base64 PNG data URI depending on output format
    """
    increment_request_count()
    
    valid_types = ["line", "bar", "scatter", "pie", "area", "histogram", "box", "heatmap", "treemap", "sunburst", "funnel", "gauge", "indicator", "bubble"]
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


@mcp.tool()
async def run_javascript(
    code: str = Field(description="JavaScript code to execute"),
    timeout_ms: int = Field(
        default=5000,
        description="Execution timeout in milliseconds (default: 5000)"
    ),
    context: dict = Field(
        default_factory=dict,
        description="Optional variables to inject into JS context as JSON-serializable dict"
    ),
) -> str:
    """Execute JavaScript code in a sandboxed V8 environment and return output.
    
    Runs JS in an isolated context. Supports ES2023 features including async/await.
    
    Built-in functions:
    - fetch(url, options?): Make HTTP requests. Returns {status, statusText, headers, body}
      - options.method: HTTP method (default: "GET")
      - options.headers: Object with request headers
      - options.body: Request body string
      - options.timeout: Timeout in ms (default: 10000)
    
    Example:
        code: "Math.pow(2, 10)"  -> returns 1024
        code: "[1,2,3].map(x => x * 2)"  -> returns [2, 4, 6]
        code: "await fetch('https://api.ipify.org?format=json').then(r => r.json())"  -> fetches data
    
    Args:
        code: JavaScript code to execute (expression or statements)
        timeout_ms: Maximum execution time in milliseconds (default 5000)
        context: Optional dict of variables to inject into the JS context
        
    Returns:
        JSON representation of the return value, or error message if execution fails
    """
    import asyncio
    import httpx
    
    increment_request_count()
    
    # Strip surrounding quotes if code is wrapped like a JSON string
    code = code.strip()
    if (code.startswith('"') and code.endswith('"')) or (code.startswith("'") and code.endswith("'")):
        code = code[1:-1]
    
    try:
        from py_mini_racer import MiniRacer
    except ImportError:
        return "Error: mini-racer not installed. Run: pip install mini-racer"
    
    async def js_fetch(url: str, options: dict = None) -> dict:
        """HTTP fetch implementation for JS context."""
        options = options or {}
        
        method = options.get("method", "GET")
        headers = options.get("headers", {})
        body = options.get("body")
        timeout = options.get("timeout", 10000) / 1000.0
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body,
                    follow_redirects=True,
                )
            
            return {
                "status": response.status_code,
                "statusText": response.reason_phrase,
                "headers": dict(response.headers),
                "body": response.text,
            }
        except httpx.TimeoutException:
            return {"error": f"Request timed out after {timeout}s", "status": 0}
        except Exception as e:
            return {"error": str(e), "status": 0}
    
    try:
        mr = MiniRacer()
        
        # Register fetch function
        mr.wrap_py_function("fetch", js_fetch)
        
        # Build the full code with context variables injected
        context_lines = []
        for key, value in context.items():
            if not key.isidentifier():
                return f"Error: Invalid context variable name '{key}'. Must be a valid JS identifier."
            context_lines.append(f"const {key} = {json.dumps(value)};")
        
        context_code = "\n".join(context_lines)
        
        # Determine if code is an expression or statement
        code_trimmed = code.strip()
        is_statement = code_trimmed.endswith((";", "}"))
        
        # Build final code
        if is_statement:
            # For statements, wrap in IIFE to capture last expression
            full_code = f"(async () => {{\n{context_code}\n{code_trimmed}\n}})()"
        else:
            # For expressions, just wrap in async IIFE
            if context_code:
                full_code = f"(async () => {{\n{context_code}\nreturn ({code_trimmed});\n}})()"
            else:
                full_code = f"(async () => {{ return ({code_trimmed}); }})()"
        
        # Execute with timeout
        timeout_sec = timeout_ms / 1000.0
        try:
            result = await asyncio.wait_for(
                mr.eval_cancelable(full_code),
                timeout=timeout_sec
            )
        except asyncio.TimeoutError:
            return f"Error: Execution timed out after {timeout_ms}ms"
        
        # Convert result to JSON string
        if result is None:
            return "null"
        
        # Handle different result types
        if isinstance(result, (str, int, float, bool, list, dict)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            # For JS objects, use JSON.stringify in the engine
            try:
                json_str = await asyncio.wait_for(
                    mr.eval_cancelable(f"JSON.stringify({json.dumps(str(result))})"),
                    timeout=1
                )
                return json_str
            except:
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
