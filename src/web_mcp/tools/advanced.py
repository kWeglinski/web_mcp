"""Advanced tools: create_chart_tool and run_javascript."""

import asyncio
import json

from web_mcp.config import get_config
from web_mcp.content_store import get_content_store
from web_mcp.logging import get_logger
from web_mcp.security import validate_url, validate_url_ip
from web_mcp.tools._core import increment_request_count

logger = get_logger(__name__)


async def create_chart_tool(
    type: str,
    data: dict,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    options: dict | None = None,
    output: str = "url",
) -> str:
    """Create interactive Plotly chart. Output as URL (requires WEB_MCP_PUBLIC_URL) or PNG image."""
    increment_request_count()

    if options is None:
        options = {}

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

    valid_outputs = ["url", "image"]
    if output not in valid_outputs:
        return f"Error: Invalid output format '{output}'. Valid formats: {', '.join(valid_outputs)}"

    config = get_config()

    if output == "url" and not config.public_url:
        return "Error: WEB_MCP_PUBLIC_URL not configured. Set it to your server's public URL for URL output."

    if output == "image" and not config.public_url:
        return "Error: WEB_MCP_PUBLIC_URL not configured. Set it to your server's public URL for image output."

    try:
        from web_mcp.charts import ChartConfig, ChartError
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
        else:
            from web_mcp.charts import create_chart
            html = create_chart(chart_config)
            store = get_content_store()
            content_id, token = store.store(html, content_type="text/html")
            url = f"{config.public_url}/c/{content_id}?token={token}"
            return url
    except ChartError as e:
        return f"Error creating chart: {e}"
    except Exception as e:
        return f"Error: {e}"


async def run_javascript(
    code: str,
    timeout_ms: int = 5000,
    context: dict | None = None,
) -> str:
    """Execute JavaScript in sandboxed V8. Supports async/await and fetch(). Has SSRF protection."""
    import httpx

    config = get_config()
    increment_request_count()

    if context is None:
        context = {}

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

    async def py_fetch(url: str, options: dict | None = None) -> str:
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
        is_statement = code_trimmed.endswith((";", "}")) or (
            code_trimmed.endswith(")")
            and not (code_trimmed.startswith("(") or code_trimmed.startswith("["))
        )

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
