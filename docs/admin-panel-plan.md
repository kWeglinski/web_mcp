# Web MCP Admin Panel — Implementation Plan

## Overview

Add an admin panel to Web MCP that enables:
1. **Path-based tool routing** — different sets of tools exposed per server path (e.g., `/search` → search-only, `/default` → all tools)
2. **Admin UI** — web interface to toggle which tools are active per path
3. **API key protection** — admin endpoints secured via `WEB_MCP_ADMIN_API_KEY`
4. **Persistent config** — JSON file storage for path/tool configurations

---

## Architecture

### Current State

```
FastMCP instance (single)
├── @mcp.tool() → 9 tools registered at module load time
├── @mcp.custom_route() → /c/{id}, /i/{id}
├── Transports: stdio, SSE (--sse), Streamable HTTP (--http)
└── Mount: all tools on one path (/sse or /mcp)
```

### Target State

```
                    ┌─────────────────────────────────────┐
                    │         Starlette App               │
                    │   (single ASGI app, port 8000)      │
                    ├─────────────────────────────────────┤
                    │  /admin/*  → Admin UI + REST API    │
                    │  /health   → Public health check    │
                    ├─────────────────────────────────────┤
                    │  /search/sse     → search_mcp        │
                    │  /search/message → search_mcp (POST) │
                    ├─────────────────────────────────────┤
                    │  /research/sse     → research_mcp    │
                    │  /research/message → research_mcp    │
                    ├─────────────────────────────────────┤
                    │  /default/sse      → default_mcp     │
                    │  /default/message  → default_mcp     │
                    └─────────────────────────────────────┘
```

**Key insight:** `FastMCP.sse_app()` returns a `Starlette` instance. We can `Mount` multiple MCP instances at different paths within a single Starlette app, plus add admin routes.

### File Structure

```
src/web_mcp/
├── server.py                    # Current — keep for backward compat
├── config.py                    # Current — add admin config vars
├── path_routing.py              # NEW — multi-MCP router, Starlette app builder
├── admin/                       # NEW — admin panel package
│   ├── __init__.py              # create_admin_routes(routing) factory
│   ├── router.py                # FastAPI router — admin API endpoints
│   ├── ui.py                    # Admin panel HTML (vanilla JS SPA)
│   ├── storage.py               # JSON file config persistence
│   ├── auth.py                  # API key middleware
│   └── schemas.py               # Pydantic models
├── tools/                       # NEW — extracted tool functions
│   ├── __init__.py              # exports all tool functions
│   ├── _core.py                 # shared state: increment_request_count, health metrics
│   ├── fetching.py              # get_page, render_html
│   ├── search.py                # search_web, brave_search, search_metrics
│   ├── utils.py                 # health, current_datetime
│   └── advanced.py              # create_chart_tool, run_javascript
└── tests/
    └── test_admin/              # NEW
        ├── __init__.py
        ├── test_storage.py
        ├── test_auth.py
        ├── test_router.py
        └── test_path_routing.py
```

---

## Phase 0: Tool Extraction (Refactor)

**Goal:** Extract tool functions from `server.py` into `tools/` module so they can be imported and registered on multiple MCP instances without duplication.

### Changes

1. **Create `src/web_mcp/tools/__init__.py`** — re-exports all tool functions
2. **Create `src/web_mcp/tools/_core.py`** — shared state:
   ```python
   _request_count: int = 0
   _cache_hits: int = 0
   SERVER_START_TIME: float = time.time()
   VERSION: str = "1.0.0"

   def increment_request_count() -> None: ...
   def increment_cache_hits() -> None: ...
   def get_health_metrics() -> dict: ...
   ```
3. **Create `src/web_mcp/tools/fetching.py`** — `get_page`, `render_html`
4. **Create `src/web_mcp/tools/search.py`** — `search_web`, `brave_search`, `search_metrics`
5. **Create `src/web_mcp/tools/utils.py`** — `health`, `current_datetime`
6. **Create `src/web_mcp/tools/advanced.py`** — `create_chart_tool`, `run_javascript`
7. **Refactor `server.py`** — import tools from `tools/` module, register on default MCP instance
8. **Update `mypy` overrides** in `pyproject.toml` — add `web_mcp.tools`

### Tool-to-Module Mapping

| Tool | Module | Dependencies |
|---|---|---|
| `get_page` | `tools/fetching.py` | fetcher, extractors, pdf_processor, security, cache, optimizer |
| `render_html` | `tools/fetching.py` | content_store, config |
| `search_web` | `tools/search.py` | searxng, security, cache, config |
| `brave_search` | `tools/search.py` | brave, security, cache, config |
| `search_metrics` | `tools/search.py` | searxng |
| `health` | `tools/utils.py` | _core (same module) |
| `current_datetime` | `tools/utils.py` | stdlib (datetime, zoneinfo) |
| `create_chart_tool` | `tools/advanced.py` | charts, content_store, config |
| `run_javascript` | `tools/advanced.py` | mini_racer, httpx, security |

### Migration Path

- **Backward compat:** `server.py` continues to work exactly as before
- The existing `mcp` FastMCP instance imports from `tools/` instead of defining inline
- No changes to tool signatures, annotations, or behavior

---

## Phase 1: Path Routing Core

**Goal:** Build the multi-MCP routing layer that mounts different toolsets at different paths.

### 1.1 `src/web_mcp/path_routing.py`

```python
"""Multi-path MCP server router.

Manages multiple FastMCP instances mapped to URL paths.
Each path gets its own toolset based on admin configuration.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount, Route


class PathConfig:
    """Configuration for one MCP path."""

    def __init__(
        self,
        path: str,
        mcp: FastMCP,
        name: str,
        description: str = "",
        enabled_tools: list[str] | None = None,
        requires_auth: bool = True,
    ):
        self.path = path.rstrip("/") or "/"
        self.mcp = mcp
        self.name = name
        self.description = description
        self.enabled_tools = enabled_tools or []
        self.requires_auth = requires_auth


class PathRouter:
    """Manages multiple MCP instances mapped to URL paths."""

    def __init__(self):
        self._configs: dict[str, PathConfig] = {}
        self._default_mcp: FastMCP | None = None

    @property
    def paths(self) -> list[str]:
        return list(self._configs.keys())

    def add_path(self, config: PathConfig) -> None:
        self._configs[config.path] = config

    def set_default(self, mcp: FastMCP) -> None:
        self._default_mcp = mcp

    def get_path_config(self, path: str) -> PathConfig | None:
        return self._configs.get(path)

    def remove_path(self, path: str) -> bool:
        return self._configs.pop(path, None) is not None

    def build_starlette_app(
        self,
        admin_routes: list[Route] | None = None,
        middleware: list[Middleware] | None = None,
    ) -> Starlette:
        """Build a single Starlette app with all MCP mounts + admin routes."""
        routes: list[Route | Mount] = []

        # Mount each MCP server at its path
        for path, config in self._configs.items():
            routes.append(Mount(path, app=config.mcp.sse_app()))

        # Default fallback
        if self._default_mcp:
            routes.append(Mount("/default", app=self._default_mcp.sse_app()))

        # Admin routes
        if admin_routes:
            routes.extend(admin_routes)

        # Health endpoint
        routes.append(Route("/health", self._health_handler, methods=["GET"]))

        return Starlette(
            routes=routes,
            middleware=middleware or [],
        )

    @staticmethod
    async def _health_handler(request):
        from starlette.responses import JSONResponse
        return JSONResponse({"status": "healthy", "version": "1.0.0"})


def validate_path(path: str) -> bool:
    """Validate that a path is URL-safe."""
    import re
    pattern = r"^/[a-zA-Z0-9_\-/]*$"
    return bool(re.match(pattern, path)) and path != "/"
```

### 1.2 Server Integration (`server.py` changes)

```python
# In server.py — after tool imports from tools/ module:

def create_default_mcp() -> FastMCP:
    """Create the default MCP instance with all tools."""
    _token_verifier, _auth_settings = create_auth_config()
    return FastMCP(
        name="web-browsing",
        instructions="Full web browsing suite...",
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
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
```

### 1.3 `main()` Update

```python
def main():
    """Run the MCP server."""
    import sys

    if "--admin" in sys.argv or os.environ.get("WEB_MCP_ADMIN_ENABLED", "").lower() in ("true", "1", "yes"):
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
```

---

## Phase 2: Admin Panel Package

### 2.1 `src/web_mcp/admin/storage.py` — Config Persistence

JSON file-backed storage with in-memory cache.

**Config file path:** `WEB_MCP_ADMIN_CONFIG_FILE` (default: `/data/mcp-admin-config.json`)

**File format:**
```json
{
  "version": 1,
  "paths": {
    "/search": {
      "name": "search-only",
      "description": "Web search tools only",
      "enabled_tools": ["search_web", "brave_search", "search_metrics"],
      "requires_auth": true
    },
    "/research": {
      "name": "research",
      "description": "Research tools",
      "enabled_tools": ["get_page", "search_web", "brave_search", "search_metrics"],
      "requires_auth": true
    },
    "/default": {
      "name": "full-suite",
      "description": "All web browsing tools",
      "enabled_tools": ["get_page", "search_web", "brave_search", "create_chart_tool", "run_javascript", "render_html", "current_datetime", "health", "search_metrics"],
      "requires_auth": true
    }
  }
}
```

**API:**
```python
class ConfigStorage:
    def __init__(self, config_path: Path | None = None)
    def save(self) -> None
    def get_paths(self) -> dict[str, Any]
    def get_path_config(self, path: str) -> dict[str, Any] | None
    def set_path_config(self, path: str, config: dict[str, Any]) -> None
    def delete_path_config(self, path: str) -> bool
    def get_all_tool_names(self) -> list[str]  # returns the 9 tool names
```

### 2.2 `src/web_mcp/admin/auth.py` — API Key Middleware

Protects `/admin/*` endpoints with `WEB_MCP_ADMIN_API_KEY`.

```python
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

ADMIN_API_KEY = os.environ.get("WEB_MCP_ADMIN_API_KEY", "")
ADMIN_PATH_PREFIX = os.environ.get("WEB_MCP_ADMIN_PATH", "/admin")

class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(ADMIN_PATH_PREFIX):
            if not ADMIN_API_KEY:
                return JSONResponse(
                    {"error": "Admin API key not configured"},
                    status_code=503,
                )
            api_key = (
                request.headers.get("X-Admin-Key")
                or request.query_params.get("api_key")
            )
            if not api_key or api_key != ADMIN_API_KEY:
                return JSONResponse(
                    {"error": "Unauthorized"},
                    status_code=401,
                )
        response = await call_next(request)
        return response
```

**Two auth headers:**
| Header | Used For | Env Var |
|---|---|---|
| `Authorization: Bearer <token>` | MCP protocol clients | `WEB_MCP_AUTH_TOKEN` |
| `X-Admin-Key: <key>` | Admin panel HTTP requests | `WEB_MCP_ADMIN_API_KEY` |

### 2.3 `src/web_mcp/admin/schemas.py` — Pydantic Models

```python
from pydantic import BaseModel, Field

ALL_TOOL_NAMES = [
    "get_page", "search_web", "brave_search",
    "create_chart_tool", "run_javascript",
    "render_html", "current_datetime", "health", "search_metrics",
]

class PathConfigIn(BaseModel):
    name: str = Field(description="Display name for this path")
    description: str = ""
    enabled_tools: list[str] = Field(
        description="List of tool names to enable",
        default_factory=list,
    )
    requires_auth: bool = True

class PathConfigOut(BaseModel):
    path: str
    name: str
    description: str
    enabled_tools: list[str]
    requires_auth: bool

class ToolInfo(BaseModel):
    name: str
    description: str
    is_read_only: bool = True
    is_destructive: bool = False

class AdminHealthOut(BaseModel):
    status: str
    version: str
    admin_enabled: bool
    admin_path: str
    configured_paths: list[str]
    available_tools: list[ToolInfo]
```

### 2.4 `src/web_mcp/admin/router.py` — Admin API Routes

```python
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()

@router.get("/admin/")
async def admin_dashboard():
    """Serve the admin panel UI."""
    from web_mcp.admin.ui import ADMIN_HTML
    return HTMLResponse(ADMIN_HTML)

@router.get("/admin/health")
async def admin_health():
    """Admin health endpoint with config summary."""
    ...

@router.get("/admin/tools")
async def list_tools():
    """List all available tools with metadata."""
    ...

@router.get("/admin/configs")
async def list_configs():
    """List all path configurations."""
    ...

@router.post("/admin/configs/{path}")
async def upsert_config(path: str, config: PathConfigIn):
    """Create or update a path configuration."""
    ...

@router.delete("/admin/configs/{path}")
async def delete_config(path: str):
    """Delete a path configuration."""
    ...

@router.get("/admin/configs/{path}/apply")
async def apply_config(path: str):
    """Apply a path config — rebuilds the MCP instance for that path."""
    ...
```

### 2.5 `src/web_mcp/admin/ui.py` — Admin Panel UI

Single-page HTML application with vanilla JS. No build step, no framework.

**Sections:**
1. **Header** — title, version, health status
2. **Tool palette** — checkbox list of all 9 tools (draggable or selectable)
3. **Path cards** — one card per configured path, showing enabled tools
4. **Add path** — form to create new path with tool selection
5. **Delete** — per-path delete button with confirmation

**Design:** Clean, minimal admin UI. No external CSS/JS dependencies. Use CSS custom properties for theming.

**Tech:** Vanilla HTML + CSS + JavaScript (fetch API, DOM manipulation). ~300-400 lines total.

### 2.6 `src/web_mcp/admin/__init__.py` — Factory

```python
"""Admin panel package."""

from web_mcp.admin.auth import AdminAuthMiddleware
from web_mcp.admin.router import router as admin_router
from web_mcp.admin.storage import ConfigStorage


def create_admin_routes(routing):
    """Create admin routes and middleware for the given PathRouter."""
    from starlette.routing import Route
    from web_mcp.admin.router import (
        admin_dashboard, admin_health, list_tools,
        list_configs, upsert_config, delete_config, apply_config,
    )

    routes = [
        Route("/", admin_dashboard, methods=["GET"]),
        Route("/health", admin_health, methods=["GET"]),
        Route("/tools", list_tools, methods=["GET"]),
        Route("/configs", list_configs, methods=["GET"]),
        Route("/configs/{path}", upsert_config, methods=["POST"]),
        Route("/configs/{path}", delete_config, methods=["DELETE"]),
        Route("/configs/{path}/apply", apply_config, methods=["GET"]),
    ]

    return routes, AdminAuthMiddleware
```

---

## Phase 3: Tool Registration by Path

**Goal:** Dynamic tool registration — build MCP instances with only the tools specified in config.

### `server.py` additions

```python
# Tool metadata registry (used by admin UI and dynamic registration)
TOOL_REGISTRY: dict[str, dict] = {
    "get_page": {
        "name": "get_page",
        "description": "Fetch and extract content from a URL",
        "is_read_only": True,
        "module": "tools.fetching",
    },
    "search_web": {
        "name": "search_web",
        "description": "Search the web using SearXNG",
        "is_read_only": True,
        "module": "tools.search",
    },
    # ... all 9 tools
}

def register_all_tools(mcp: FastMCP) -> None:
    """Register all tools on an MCP instance."""
    from web_mcp.tools.fetching import get_page, render_html
    from web_mcp.tools.search import search_web, brave_search, search_metrics
    from web_mcp.tools.utils import health, current_datetime
    from web_mcp.tools.advanced import create_chart_tool, run_javascript

    _register_tool(mcp, get_page)
    _register_tool(mcp, render_html)
    _register_tool(mcp, search_web)
    _register_tool(mcp, brave_search)
    _register_tool(mcp, search_metrics)
    _register_tool(mcp, health)
    _register_tool(mcp, current_datetime)
    _register_tool(mcp, create_chart_tool)
    _register_tool(mcp, run_javascript)


def register_tools_for_path(mcp: FastMCP, tool_names: list[str]) -> None:
    """Register only the specified tools on an MCP instance."""
    all_tools = {
        "get_page": tools.fetching.get_page,
        "render_html": tools.fetching.render_html,
        "search_web": tools.search.search_web,
        "brave_search": tools.search.brave_search,
        "search_metrics": tools.search.search_metrics,
        "health": tools.utils.health,
        "current_datetime": tools.utils.current_datetime,
        "create_chart_tool": tools.advanced.create_chart_tool,
        "run_javascript": tools.advanced.run_javascript,
    }

    for name in tool_names:
        tool_fn = all_tools.get(name)
        if tool_fn is None:
            logger.warning(f"Unknown tool '{name}', skipping")
            continue
        _register_tool(mcp, tool_fn)


def _register_tool(mcp: FastMCP, fn) -> None:
    """Register a tool function on an MCP instance with proper annotations."""
    # The @mcp.tool() decorator needs to be applied dynamically
    # Since tools are already decorated at module level, we need to
    # use the underlying MCP tool registration mechanism
    mcp.add_tool(fn)
```

**Note:** `FastMCP` exposes `add_tool()` for programmatic registration. If not available, we may need to re-apply the `@mcp.tool()` decorator in `register_*_tools()` functions.

---

## Phase 4: Configuration & Environment

### New Environment Variables

Add to `.env.example`:

```bash
# Admin Panel
# Enable admin panel (--admin flag or this env var)
WEB_MCP_ADMIN_ENABLED=false

# API key for admin panel endpoints (separate from WEB_MCP_AUTH_TOKEN)
WEB_MCP_ADMIN_API_KEY=

# Path prefix for admin endpoints
WEB_MCP_ADMIN_PATH=/admin

# Path to admin config JSON file
WEB_MCP_ADMIN_CONFIG_FILE=/data/mcp-admin-config.json
```

### Config Update in `config.py`

```python
# In Config class:
@property
def admin_enabled(self) -> bool:
    return os.environ.get("WEB_MCP_ADMIN_ENABLED", "").lower() in ("true", "1", "yes")

@property
def admin_api_key(self) -> str:
    return os.environ.get("WEB_MCP_ADMIN_API_KEY", "")

@property
def admin_path(self) -> str:
    return os.environ.get("WEB_MCP_ADMIN_PATH", "/admin")

@property
def admin_config_file(self) -> str:
    return os.environ.get("WEB_MCP_ADMIN_CONFIG_FILE", "/data/mcp-admin-config.json")
```

---

## Phase 5: Dependencies

### New Dependencies (`pyproject.toml`)

```toml
dependencies = [
    # ... existing ...
    "fastapi>=0.115.0",      # Admin API framework
    "jinja2>=3.1.0",         # HTML templating (for admin UI)
]
```

**Note:** `mcp` already depends on `starlette` and `uvicorn`, so no new ASGI server needed. `fastapi` is lightweight on top of Starlette.

### Mypy Override

```toml
[[tool.mypy.overrides]]
module = [
    # ... existing ...
    "web_mcp.admin.*",
    "web_mcp.path_routing",
    "web_mcp.tools.*",
]
ignore_errors = true
```

---

## Phase 6: Tests

### Test Structure

```
tests/test_admin/
├── __init__.py
├── test_storage.py          # ConfigStorage CRUD operations
├── test_auth.py             # AdminAuthMiddleware
├── test_router.py           # Admin API endpoints
├── test_path_routing.py     # PathRouter, build_starlette_app
└── test_tool_registration.py # register_all_tools, register_tools_for_path
```

### Test Coverage Targets

| Module | Target |
|---|---|
| `admin/storage.py` | 80% |
| `admin/auth.py` | 80% |
| `admin/router.py` | 60% |
| `path_routing.py` | 70% |
| `tools/` | 0% (tool logic unchanged, existing tests cover) |

### Key Test Cases

**`test_storage.py`:**
- `test_save_and_load` — write config, reload, verify
- `test_default_empty_config` — no file → empty paths
- `test_corrupt_file` — bad JSON → fallback to empty
- `test_upsert_and_delete` — full CRUD cycle

**`test_auth.py`:**
- `test_valid_key` — correct key → 200
- `test_invalid_key` — wrong key → 401
- `test_missing_key` — no header → 401
- `test_non_admin_path` — `/health` bypasses auth

**`test_path_routing.py`:**
- `test_build_app` — verify Starlette app has correct routes
- `test_mount_paths` — verify MCP instances mounted at correct paths
- `test_default_fallback` — verify default MCP is mounted

**`test_router.py`:**
- `test_list_tools` — returns all 9 tools
- `test_upsert_config` — creates new path config
- `test_delete_config` — removes path config
- `test_invalid_path` — rejects invalid paths

---

## Implementation Order

```
Phase 0: Tool Extraction (Refactor)
  ├── Create tools/ module structure
  ├── Move tool functions from server.py to tools/
  ├── Update server.py to import from tools/
  └── Ensure existing tests still pass

Phase 1: Path Routing Core
  ├── Create path_routing.py
  ├── Update server.py main() with --admin flag
  └── Quick smoke test: two MCP instances at /search and /default

Phase 2: Admin Panel Package
  ├── Create admin/storage.py (JSON persistence)
  ├── Create admin/auth.py (API key middleware)
  ├── Create admin/schemas.py (Pydantic models)
  ├── Create admin/router.py (FastAPI routes)
  ├── Create admin/ui.py (Admin HTML)
  └── Create admin/__init__.py (factory)

Phase 3: Tool Registration by Path
  ├── Implement register_all_tools()
  ├── Implement register_tools_for_path()
  └── Wire admin config → dynamic MCP instance creation

Phase 4: Configuration
  ├── Add new env vars to config.py
  ├── Update .env.example
  └── Add to pyproject.toml dependencies

Phase 5: Tests
  ├── test_admin/storage.py
  ├── test_admin/auth.py
  ├── test_admin/router.py
  ├── test_admin/path_routing.py
  └── Integration tests

Phase 6: Polish
  ├── Update mypy overrides
  ├── Run make check (lint + format + typecheck + test)
  ├── Update README.md
  └── Dockerfile update (admin config volume)
```

---

## Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| `FastMCP.sse_app()` doesn't support mounting under sub-paths | Medium | Test early. If it fails, use `--path-prefix` or create custom SSE handler |
| Tool decorator can't be re-applied dynamically | Low | `FastMCP` has `add_tool()` — verify in docs. Fallback: apply `@mcp.tool()` at module level in each `tools/` file |
| Config reload requires server restart | Low | Phase 3+ adds hot-reload; Phase 1-2 can restart |
| Tool extraction breaks existing behavior | High | Comprehensive tests in Phase 0; keep `server.py` as integration layer |
| JSON config race condition (two writes) | Low | File locking or accept last-write-wins for admin config |

---

## Future Extensions (Out of Scope)

- **Hot-reload** — file watcher on config JSON, live MCP instance rebuild
- **Config export/import** — download/upload config JSON
- **Audit log** — track all admin changes with timestamps
- **Role-based access** — read-only vs admin roles
- **Metrics per path** — track request counts per path/toolset
- **YAML config** — support YAML as alternative to JSON
- **Docker Compose** — pre-configured admin panel with docker-compose
- **HTTPS/TLS** — built-in TLS for admin panel
