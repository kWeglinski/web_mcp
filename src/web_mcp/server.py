"""Web Browsing MCP Server - Browse the web with context-aware content extraction."""

import os
import sys
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from web_mcp.content_store import get_content_store, start_cleanup_task, stop_cleanup_task
from web_mcp.logging import get_logger, setup_logging

setup_logging()

logger = get_logger(__name__)


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
    from pydantic import AnyHttpUrl

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


SERVER_HOST = os.environ.get("WEB_MCP_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("WEB_MCP_SERVER_PORT", "8000"))

OUTPUT_SCHEMAS = os.environ.get("WEB_MCP_OUTPUT_SCHEMAS", "").lower() in ("true", "1", "yes")

setup_logging()

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app):
    start_cleanup_task()
    try:
        yield
    finally:
        stop_cleanup_task()


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


# ---------------------------------------------------------------------------
# Tool registry and registration
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, dict] = {
    "get_page": {
        "name": "get_page",
        "description": "Fetch and extract content from a URL",
        "is_read_only": True,
        "module": "tools.fetching",
    },
    "render_html": {
        "name": "render_html",
        "description": "Store HTML body content and return a viewable URL",
        "is_read_only": True,
        "module": "tools.fetching",
    },
    "search_web": {
        "name": "search_web",
        "description": "Search the web using SearXNG",
        "is_read_only": True,
        "module": "tools.search",
    },
    "brave_search": {
        "name": "brave_search",
        "description": "Search the web via Brave Search API",
        "is_read_only": True,
        "module": "tools.search",
    },
    "search_metrics": {
        "name": "search_metrics",
        "description": "Get search analytics",
        "is_read_only": True,
        "module": "tools.search",
    },
    "health": {
        "name": "health",
        "description": "Get server health metrics",
        "is_read_only": True,
        "module": "tools.utils",
    },
    "current_datetime": {
        "name": "current_datetime",
        "description": "Get current date/time in specified timezone",
        "is_read_only": True,
        "module": "tools.utils",
    },
    "create_chart_tool": {
        "name": "create_chart_tool",
        "description": "Create interactive Plotly chart",
        "is_read_only": False,
        "module": "tools.advanced",
    },
    "run_javascript": {
        "name": "run_javascript",
        "description": "Execute JavaScript in sandboxed V8",
        "is_read_only": False,
        "destructive": True,
        "module": "tools.advanced",
    },
}


def _register_tool(mcp, fn, annotations=None, structured_output=False) -> None:
    """Register a tool function on an MCP instance."""
    mcp.add_tool(fn, annotations=annotations, structured_output=structured_output)


def register_all_tools(mcp: FastMCP) -> None:
    """Register all tools on an MCP instance."""
    from web_mcp.tools.advanced import create_chart_tool, run_javascript
    from web_mcp.tools.fetching import get_page, render_html
    from web_mcp.tools.search import brave_search, search_metrics, search_web
    from web_mcp.tools.utils import current_datetime, health

    ro = ToolAnnotations(readOnlyHint=True)
    ro_ow = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
    ro_destructive = ToolAnnotations(destructiveHint=True, openWorldHint=True)

    _register_tool(mcp, get_page, ro_ow, OUTPUT_SCHEMAS)
    _register_tool(mcp, render_html, ro, OUTPUT_SCHEMAS)
    _register_tool(mcp, search_web, ro_ow, OUTPUT_SCHEMAS)
    _register_tool(mcp, brave_search, ro_ow, OUTPUT_SCHEMAS)
    _register_tool(mcp, search_metrics, ro, None)
    _register_tool(mcp, health, ro, OUTPUT_SCHEMAS)
    _register_tool(mcp, current_datetime, ro, OUTPUT_SCHEMAS)
    _register_tool(mcp, create_chart_tool, ToolAnnotations(openWorldHint=True), OUTPUT_SCHEMAS)
    _register_tool(mcp, run_javascript, ro_destructive, OUTPUT_SCHEMAS)


def register_tools_for_path(mcp: FastMCP, tool_names: list[str]) -> None:
    """Register only the specified tools on an MCP instance."""
    from web_mcp.tools import advanced, fetching, search, utils

    all_tools: dict[str, tuple] = {
        "get_page": (
            fetching.get_page,
            ToolAnnotations(readOnlyHint=True, openWorldHint=True),
            OUTPUT_SCHEMAS,
        ),
        "render_html": (fetching.render_html, ToolAnnotations(readOnlyHint=True), OUTPUT_SCHEMAS),
        "search_web": (
            search.search_web,
            ToolAnnotations(readOnlyHint=True, openWorldHint=True),
            OUTPUT_SCHEMAS,
        ),
        "brave_search": (
            search.brave_search,
            ToolAnnotations(readOnlyHint=True, openWorldHint=True),
            OUTPUT_SCHEMAS,
        ),
        "search_metrics": (search.search_metrics, ToolAnnotations(readOnlyHint=True), None),
        "health": (utils.health, ToolAnnotations(readOnlyHint=True), OUTPUT_SCHEMAS),
        "current_datetime": (
            utils.current_datetime,
            ToolAnnotations(readOnlyHint=True),
            OUTPUT_SCHEMAS,
        ),
        "create_chart_tool": (
            advanced.create_chart_tool,
            ToolAnnotations(openWorldHint=True),
            OUTPUT_SCHEMAS,
        ),
        "run_javascript": (
            advanced.run_javascript,
            ToolAnnotations(destructiveHint=True, openWorldHint=True),
            OUTPUT_SCHEMAS,
        ),
    }

    for name in tool_names:
        tool_entry = all_tools.get(name)
        if tool_entry is None:
            logger.warning(f"Unknown tool '{name}', skipping")
            continue
        fn, annotations, structured_output = tool_entry
        _register_tool(mcp, fn, annotations, structured_output)


def create_default_mcp() -> FastMCP:
    """Create the default MCP instance with all tools."""
    _token_verifier, _auth_settings = create_auth_config()
    return FastMCP(
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


def build_admin_mode() -> None:
    """Build and run in admin/multi-path mode."""
    from web_mcp.admin import create_admin_routes
    from web_mcp.admin.storage import ConfigStorage
    from web_mcp.path_routing import PathConfig, PathRouter, validate_path

    routing = PathRouter()

    # Create default MCP with all tools
    default_mcp = create_default_mcp()
    register_all_tools(default_mcp)  # imports from tools/
    routing.set_default(default_mcp)

    # Load admin config and build path-specific MCPs
    storage = ConfigStorage()
    config = storage.get_paths()
    for path, path_config in config.items():
        if not validate_path(path):
            continue
        mcp = FastMCP(name=f"web-mcp-{path.lstrip('/')}")
        register_tools_for_path(mcp, path_config.get("enabled_tools", []))
        routing.add_path(PathConfig(path, mcp, path_config.get("name", path)))

    # Build admin routes
    admin_routes = create_admin_routes(routing)

    # Build Starlette app
    app = routing.build_starlette_app(admin_routes)

    # Run with uvicorn
    import uvicorn

    logger.info(f"Starting admin mode on http://{SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)


def main():
    """Run the MCP server."""
    import sys

    if "--admin" in sys.argv or os.environ.get("WEB_MCP_ADMIN_ENABLED", "").lower() in (
        "true",
        "1",
        "yes",
    ):
        build_admin_mode()
        return

    tools = "get_page, search_web, brave_search, create_chart_tool, render_html, current_datetime, health, run_javascript, search_metrics"

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
