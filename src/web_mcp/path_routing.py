"""Multi-path MCP server router.

Manages multiple FastMCP instances mapped to URL paths.
Each path gets its own toolset based on admin configuration.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount, Route

from web_mcp.logging import get_logger

logger = get_logger(__name__)


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
        self._app: Starlette | None = None

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

    def refresh_from_storage(self) -> None:
        """Reload all paths from ConfigStorage into _configs."""
        from mcp.server.transport_security import TransportSecuritySettings

        from web_mcp.admin.storage import ConfigStorage
        from web_mcp.server import (
            SERVER_HOST,
            SERVER_PORT,
            create_auth_config,
            register_tools_for_path,
        )

        storage = ConfigStorage()
        for path, path_config in storage.get_paths().items():
            if path in self._configs:
                continue
            requires_auth = path_config.get("requires_auth", True)
            token_verifier = None
            auth = None
            if requires_auth:
                token_verifier, auth = create_auth_config()
            mcp = FastMCP(
                name=f"web-mcp-{path.lstrip('/')}",
                host=SERVER_HOST,
                port=SERVER_PORT,
                transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
                token_verifier=token_verifier,
                auth=auth,
            )
            register_tools_for_path(mcp, path_config.get("enabled_tools", []))
            self.add_path(
                PathConfig(
                    path,
                    mcp,
                    path_config.get("name", path),
                    path_config.get("description", ""),
                    path_config.get("enabled_tools", []),
                    requires_auth,
                )
            )

    def register_path(self, path: str, config_dict: dict) -> None:
        """Register a single path at runtime and add its route to the app."""
        from mcp.server.transport_security import TransportSecuritySettings

        from web_mcp.server import (
            SERVER_HOST,
            SERVER_PORT,
            create_auth_config,
            register_tools_for_path,
        )

        requires_auth = config_dict.get("requires_auth", True)
        token_verifier = None
        auth = None
        if requires_auth:
            token_verifier, auth = create_auth_config()
        mcp = FastMCP(
            name=f"web-mcp-{path.lstrip('/')}",
            host=SERVER_HOST,
            port=SERVER_PORT,
            transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
            token_verifier=token_verifier,
            auth=auth,
        )
        register_tools_for_path(mcp, config_dict.get("enabled_tools", []))
        pc = PathConfig(
            path,
            mcp,
            config_dict.get("name", path),
            config_dict.get("description", ""),
            config_dict.get("enabled_tools", []),
            requires_auth,
        )
        self.add_path(pc)
        self._mount_path_to_app(pc)

    def unregister_path(self, path: str) -> bool:
        """Remove a path from _configs and its routes from the app."""
        removed = self.remove_path(path)
        if removed and self._app is not None:
            self._remove_path_from_app(path)
        return removed

    def _mount_path_to_app(self, config: PathConfig) -> None:
        """Mount a path's MCP app into the running Starlette app's routes."""
        if self._app is None:
            return
        path = config.path
        self._app.routes.append(Mount(path, app=config.mcp.sse_app()))

    def _remove_path_from_app(self, path: str) -> None:
        """Remove a path's routes from the running Starlette app."""
        if self._app is None:
            return
        self._app.routes = [
            r for r in self._app.routes if not (hasattr(r, "path") and r.path == path)
        ]

    def build_starlette_app(
        self,
        admin_routes: list[Route] | None = None,
        middleware: list[Middleware] | None = None,
    ) -> Starlette:
        """Build a single Starlette app with all MCP mounts + admin routes.

        Admin routes are added BEFORE MCP mounts so they take priority
        and are not intercepted by MCP's route matching.
        """
        routes: list[Route | Mount] = []

        # Admin routes FIRST so they take priority over MCP mounts
        if admin_routes:
            routes.extend(admin_routes)

        # Mount each MCP server at its path
        for path, config in self._configs.items():
            routes.append(Mount(path, app=config.mcp.sse_app()))

        # Default fallback
        if self._default_mcp:
            routes.append(Mount("/default", app=self._default_mcp.sse_app()))

        # Health endpoint
        routes.append(Route("/health", self._health_handler, methods=["GET"]))

        app = Starlette(
            routes=routes,
            middleware=middleware or [],
        )
        self._app = app
        return app

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
    try:
        from web_mcp.server import TOOL_REGISTRY

        return list(TOOL_REGISTRY.keys())
    except Exception:
        return []


def get_tool_descriptions() -> dict[str, str]:
    """Return a dict mapping tool names to their descriptions."""
    try:
        from web_mcp.server import TOOL_REGISTRY

        return {name: info["description"] for name, info in TOOL_REGISTRY.items()}
    except Exception:
        logger.warning(
            "Failed to load tool descriptions — TOOL_REGISTRY unavailable", exc_info=True
        )
        return {}
