"""Utility tools: health and current_datetime."""

from datetime import UTC
from typing import Any

from web_mcp.tools._core import get_health_metrics, increment_request_count


async def health() -> dict[str, Any]:
    """Get server health metrics: cache hit rate, request count, uptime."""
    increment_request_count()
    return get_health_metrics()


async def current_datetime(
    timezone: str = "UTC",
    format: str = "iso",
) -> str:
    """Get current date/time in specified timezone. Formats: iso, unix, readable."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    increment_request_count()

    try:
        if timezone.upper() == "UTC":
            now = datetime.now(UTC)
        else:
            tz_info = ZoneInfo(timezone)
            now = datetime.now(tz_info)

        if format == "unix":
            return str(int(now.timestamp()))
        elif format == "readable":
            return now.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z")
        else:
            return now.isoformat()
    except Exception as e:
        return f"Error: {e}"
