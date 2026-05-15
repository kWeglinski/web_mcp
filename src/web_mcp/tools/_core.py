"""Shared state and utilities for Web MCP tools.

This module holds global counters, server metadata, and health metrics
that are shared across all tool modules.
"""

import os
import time

SERVER_START_TIME: float = time.time()
VERSION: str = "1.0.0"
_SEARCH_PROVIDER: str = os.getenv("WEB_MCP_SEARCH_PROVIDER", "searxng")  # searxng or brave

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

    total_requests = _request_count + _cache_hits
    cache_hit_rate = (_cache_hits / total_requests) if total_requests > 0 else 0.0

    from web_mcp.searxng import get_search_metrics

    search = get_search_metrics()

    return {
        "status": "healthy",
        "version": VERSION,
        "cache_hit_rate": round(cache_hit_rate, 4),
        "request_count": _request_count,
        "uptime_seconds": round(uptime, 2),
        "search": search,
    }
