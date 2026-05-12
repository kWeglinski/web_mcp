"""Web MCP tool functions.

Extracted from server.py for use with path-based routing.
Each function is registered on an MCP instance via the register_*_tools() functions.
"""

from web_mcp.tools.advanced import create_chart_tool, run_javascript
from web_mcp.tools.fetching import get_page, render_html
from web_mcp.tools.search import brave_search, search_metrics, search_web
from web_mcp.tools.utils import current_datetime, health

__all__ = [
    "get_page",
    "render_html",
    "search_web",
    "brave_search",
    "search_metrics",
    "health",
    "current_datetime",
    "create_chart_tool",
    "run_javascript",
]
