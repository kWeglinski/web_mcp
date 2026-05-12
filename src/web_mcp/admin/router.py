"""Admin API router — REST endpoints for managing path/tool configurations."""

from __future__ import annotations

import urllib.parse

from starlette.requests import Request
from starlette.responses import JSONResponse

from web_mcp.admin.schemas import (
    ConfigOutput,
    HealthOutput,
    PathConfigInput,
    PathConfigOutput,
    ToolInfo,
    ToolsListOutput,
)
from web_mcp.admin.storage import ConfigStorage
from web_mcp.path_routing import PathRouter, get_all_tool_names, get_tool_descriptions, validate_path


class AdminRouter:
    """Handles all admin API endpoints."""

    def __init__(self, routing: PathRouter):
        self._routing = routing
        self._storage = ConfigStorage()

    async def _check_auth(self, request: Request, handler):
        """Internal auth check — used by __init__.py wrapper."""
        return await handler()

    async def get_config(self, request: Request) -> JSONResponse:
        """GET /admin/config — Get full admin config."""
        paths = self._storage.get_paths()
        path_outputs = {}
        for path, config in paths.items():
            path_outputs[path] = PathConfigOutput(**config).model_dump()
        return JSONResponse(ConfigOutput(paths=path_outputs).model_dump())

    async def update_config(self, request: Request) -> JSONResponse:
        """POST /admin/config — Update full config (replaces all paths)."""
        body = await request.json()
        paths = body.get("paths", {})
        
        # Clear existing paths
        existing = list(self._storage.get_paths().keys())
        for path in existing:
            self._storage.delete_path_config(path)
        
        # Set new paths
        for path, config in paths.items():
            if not validate_path(path):
                return JSONResponse(
                    {"error": f"Invalid path: {path}"},
                    status_code=400,
                )
            self._storage.set_path_config(path, config)
        return JSONResponse({"status": "ok", "paths": len(paths)})

    async def list_paths(self, request: Request) -> JSONResponse:
        """GET /admin/config/paths — List all configured paths."""
        paths = self._storage.get_paths()
        result = {}
        for path, config in paths.items():
            result[path] = PathConfigOutput(**config).model_dump()
        return JSONResponse(result)

    async def create_path(self, request: Request) -> JSONResponse:
        """POST /admin/config/paths — Create a new path configuration."""
        body = await request.json()
        path = body.get("path")
        if not path:
            return JSONResponse({"error": "path is required"}, status_code=400)

        # URL-decode the path
        path = urllib.parse.unquote(path)

        if not validate_path(path):
            return JSONResponse(
                {"error": f"Invalid path: {path}"},
                status_code=400,
            )

        # Validate tool names
        all_tools = set(self._storage.get_all_tool_names())
        enabled_tools = body.get("enabled_tools", [])
        for tool in enabled_tools:
            if tool not in all_tools:
                return JSONResponse(
                    {"error": f"Unknown tool: {tool}"},
                    status_code=400,
                )

        try:
            config = PathConfigInput(**{k: v for k, v in body.items() if k != "path"})
        except Exception:
            return JSONResponse({"error": "Invalid path configuration"}, status_code=422)

        self._storage.set_path_config(path, config.model_dump())
        return JSONResponse({"status": "created", "path": path}, status_code=201)

    async def get_path(self, request: Request) -> JSONResponse:
        """GET /admin/config/paths/{path} — Get a specific path configuration."""
        path = urllib.parse.unquote(request.path_params["path"])
        config = self._storage.get_path_config(path)
        if config is None:
            return JSONResponse({"error": f"Path not found: {path}"}, status_code=404)
        return JSONResponse(PathConfigOutput(**config).model_dump())

    async def update_path(self, request: Request) -> JSONResponse:
        """PUT /admin/config/paths/{path} — Update a path configuration."""
        path = urllib.parse.unquote(request.path_params["path"])
        existing = self._storage.get_path_config(path)
        if existing is None:
            return JSONResponse({"error": f"Path not found: {path}"}, status_code=404)

        body = await request.json()
        # Validate tool names
        all_tools = set(self._storage.get_all_tool_names())
        enabled_tools = body.get("enabled_tools", existing.get("enabled_tools", []))
        for tool in enabled_tools:
            if tool not in all_tools:
                return JSONResponse(
                    {"error": f"Unknown tool: {tool}"},
                    status_code=400,
                )

        updated = {**existing, **{k: v for k, v in body.items() if k != "path"}}
        self._storage.set_path_config(path, updated)
        return JSONResponse({"status": "updated", "path": path})

    async def delete_path(self, request: Request) -> JSONResponse:
        """DELETE /admin/config/paths/{path} — Delete a path configuration."""
        path = urllib.parse.unquote(request.path_params["path"])
        success = self._storage.delete_path_config(path)
        if not success:
            return JSONResponse({"error": f"Path not found: {path}"}, status_code=404)
        return JSONResponse({"status": "deleted", "path": path})

    async def list_tools(self, request: Request) -> JSONResponse:
        """GET /admin/tools — List all available tools with descriptions."""
        descriptions = get_tool_descriptions()
        tools = []
        for name, desc in descriptions.items():
            is_read_only = name not in ("create_chart_tool", "run_javascript")
            destructive = name == "run_javascript"
            tools.append(ToolInfo(
                name=name,
                description=desc,
                is_read_only=is_read_only,
                destructive=destructive,
            ).model_dump())
        return JSONResponse(ToolsListOutput(tools=tools).model_dump())

    async def health(self, request: Request) -> JSONResponse:
        """GET /admin/health — Health check (no auth required)."""
        return JSONResponse(
            HealthOutput(
                status="healthy",
                version="1.0.0",
                admin_enabled=True,
            ).model_dump()
        )
