"""Admin panel — entry point.

Exports `create_admin_routes(routing)` which builds a list of Starlette
Route objects for the admin UI and REST API.
"""

from __future__ import annotations

from starlette.routing import Route

from web_mcp.path_routing import PathRouter


def create_admin_routes(routing: PathRouter) -> list[Route]:
    """Create admin panel routes for the given PathRouter.

    Args:
        routing: The PathRouter instance managing MCP path configs.

    Returns:
        List of Starlette Route objects for admin endpoints.
    """
    from web_mcp.admin.router import AdminRouter
    from web_mcp.admin.session_auth import AdminSessionMiddleware, LoginHandler
    from web_mcp.admin.ui import AdminUI

    admin_router = AdminRouter(routing)
    admin_ui = AdminUI()

    routes: list[Route] = [
        # Login page (no auth required)
        Route("/admin/login", admin_ui.serve_login, methods=["GET"]),
        # Login endpoint (no auth required)
        Route("/admin/login", LoginHandler.handle_login, methods=["POST"]),
        # Logout endpoint (no auth required)
        Route("/admin/logout", LoginHandler.handle_logout, methods=["POST"]),
        # Admin UI (requires session)
        Route("/admin", admin_ui.serve_index, methods=["GET"]),
        Route("/admin/", admin_ui.serve_index, methods=["GET"]),
        # REST API endpoints (require session)
        Route("/admin/config", admin_router.get_config, methods=["GET"]),
        Route("/admin/config", admin_router.update_config, methods=["POST"]),
        Route("/admin/config/paths", admin_router.list_paths, methods=["GET"]),
        Route("/admin/config/paths", admin_router.create_path, methods=["POST"]),
        Route("/admin/config/paths/{path:path}", admin_router.get_path, methods=["GET"]),
        Route("/admin/config/paths/{path:path}", admin_router.update_path, methods=["PUT"]),
        Route("/admin/config/paths/{path:path}", admin_router.delete_path, methods=["DELETE"]),
        Route("/admin/tools", admin_router.list_tools, methods=["GET"]),
        Route("/admin/health", admin_router.health, methods=["GET"]),
    ]

    return routes, admin_router, admin_ui, [AdminSessionMiddleware]
