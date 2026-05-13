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
from web_mcp.logging import get_logger
from web_mcp.path_routing import (
    PathRouter,
    get_tool_descriptions,
    validate_path,
)

logger = get_logger(__name__)


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
        try:
            paths = self._storage.get_paths()
            path_outputs = {}
            for path, config in paths.items():
                path_outputs[path] = PathConfigOutput(**config).model_dump()
            return JSONResponse(ConfigOutput(paths=path_outputs).model_dump())
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def update_config(self, request: Request) -> JSONResponse:
        """POST /admin/config — Update full config (replaces all paths)."""
        try:
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
            # Sync routing: remove paths no longer in config, add new ones
            for old_path in list(self._routing.paths):
                if old_path not in paths:
                    self._routing.unregister_path(old_path)
            for path, config in paths.items():
                if path not in self._routing.paths:
                    self._routing.register_path(path, config)
            return JSONResponse({"status": "ok", "paths": len(paths)})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def list_paths(self, request: Request) -> JSONResponse:
        """GET /admin/config/paths — List all configured paths."""
        try:
            paths = self._storage.get_paths()
            result = {}
            for path, config in paths.items():
                result[path] = PathConfigOutput(**config).model_dump()
            return JSONResponse(result)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def create_path(self, request: Request) -> JSONResponse:
        """POST /admin/config/paths — Create a new path configuration."""
        try:
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
            self._routing.register_path(path, config.model_dump())
            return JSONResponse({"status": "created", "path": path}, status_code=201)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def get_path(self, request: Request) -> JSONResponse:
        """GET /admin/config/paths/{path} — Get a specific path configuration."""
        try:
            path = urllib.parse.unquote(request.path_params["path"])
            config = self._storage.get_path_config(path)
            if config is None:
                return JSONResponse({"error": f"Path not found: {path}"}, status_code=404)
            return JSONResponse(PathConfigOutput(**config).model_dump())
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def update_path(self, request: Request) -> JSONResponse:
        """PUT /admin/config/paths/{path} — Update a path configuration."""
        try:
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
            self._routing.unregister_path(path)
            self._routing.register_path(path, updated)
            return JSONResponse({"status": "updated", "path": path})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def delete_path(self, request: Request) -> JSONResponse:
        """DELETE /admin/config/paths/{path} — Delete a path configuration."""
        try:
            path = urllib.parse.unquote(request.path_params["path"])
            success = self._storage.delete_path_config(path)
            if not success:
                return JSONResponse({"error": f"Path not found: {path}"}, status_code=404)
            self._routing.unregister_path(path)
            return JSONResponse({"status": "deleted", "path": path})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def list_tools(self, request: Request) -> JSONResponse:
        """GET /admin/tools — List all available tools with descriptions."""
        try:
            descriptions = get_tool_descriptions()
            if not descriptions:
                logger.warning("No tool descriptions found — admin tools list will be empty")
            tools = []
            for name, desc in descriptions.items():
                is_read_only = name not in ("create_chart_tool", "run_javascript")
                destructive = name == "run_javascript"
                tools.append(
                    ToolInfo(
                        name=name,
                        description=desc,
                        is_read_only=is_read_only,
                        destructive=destructive,
                    ).model_dump()
                )
            return JSONResponse(ToolsListOutput(tools=tools).model_dump())
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def health(self, request: Request) -> JSONResponse:
        """GET /admin/health — Health check (no auth required)."""
        return JSONResponse(
            HealthOutput(
                status="healthy",
                version="1.0.0",
                admin_enabled=True,
            ).model_dump()
        )
