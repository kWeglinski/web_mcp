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
        """Return all registered path prefixes."""
        return list(self._configs.keys())

    def add_path(self, config: PathConfig) -> None:
        """Register a path-specific MCP instance."""
        self._configs[config.path] = config

    def set_default(self, mcp: FastMCP) -> None:
        """Set the default MCP instance (mounted at /default)."""
        self._default_mcp = mcp

    def get_path_config(self, path: str) -> PathConfig | None:
        """Get configuration for a specific path."""
        return self._configs.get(path)

    def remove_path(self, path: str) -> bool:
        """Remove a path configuration. Returns True if it existed."""
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
    """Validate that a path is URL-safe.

    Args:
        path: URL path to validate

    Returns:
        True if the path is valid
    """
    import re

    pattern = r"^/[a-zA-Z0-9_\-/]*$"
    return bool(re.match(pattern, path)) and path != "/"


def get_all_tool_names() -> list[str]:
    """Return the list of all available tool names."""
    from web_mcp.server import TOOL_REGISTRY

    return list(TOOL_REGISTRY.keys())


def get_tool_descriptions() -> dict[str, str]:
    """Return a dict mapping tool names to their descriptions."""
    from web_mcp.server import TOOL_REGISTRY

    return {name: info["description"] for name, info in TOOL_REGISTRY.items()}
