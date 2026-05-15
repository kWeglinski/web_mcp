"""Unit tests for utility tools (health, current_datetime)."""

from unittest.mock import patch

import pytest


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_returns_metrics(self):
        from web_mcp.tools.utils import health

        with (
            patch("web_mcp.tools.utils.increment_request_count"),
            patch("web_mcp.tools.utils.get_health_metrics") as mock_metrics,
        ):
            mock_metrics.return_value = {
                "status": "healthy",
                "version": "1.0.0",
                "cache_hit_rate": 0.5,
                "request_count": 10,
                "uptime_seconds": 120.5,
                "search": {},
            }

            result = await health()
            assert result["status"] == "healthy"
            assert result["version"] == "1.0.0"
            assert result["request_count"] == 10
            mock_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_increments_count(self):
        from web_mcp.tools.utils import health

        with patch("web_mcp.tools.utils.get_health_metrics") as mock_metrics:
            mock_metrics.return_value = {"status": "healthy", "request_count": 0, "search": {}}

            await health()

            # Verify increment_request_count was called (it's patched at module level)
            from web_mcp.tools._core import _request_count

            assert _request_count >= 1


class TestCurrentDateTime:
    @pytest.mark.asyncio
    async def test_current_datetime_utc_iso(self):
        from web_mcp.tools.utils import current_datetime

        with patch("web_mcp.tools.utils.increment_request_count"):
            result = await current_datetime(timezone="UTC", format="iso")
            assert "T" in result
            assert "202" in result

    @pytest.mark.asyncio
    async def test_current_datetime_utc_unix(self):
        from web_mcp.tools.utils import current_datetime

        with patch("web_mcp.tools.utils.increment_request_count"):
            result = await current_datetime(timezone="UTC", format="unix")
            assert result.isdigit()
            assert len(result) == 10

    @pytest.mark.asyncio
    async def test_current_datetime_readable(self):
        from web_mcp.tools.utils import current_datetime

        with patch("web_mcp.tools.utils.increment_request_count"):
            result = await current_datetime(timezone="UTC", format="readable")
            assert "," in result
            assert "202" in result
            assert "AM" in result or "PM" in result

    @pytest.mark.asyncio
    async def test_current_datetime_default_format(self):
        from web_mcp.tools.utils import current_datetime

        with patch("web_mcp.tools.utils.increment_request_count"):
            result = await current_datetime()
            assert "T" in result

    @pytest.mark.asyncio
    async def test_current_datetime_timezone(self):
        from web_mcp.tools.utils import current_datetime

        with patch("web_mcp.tools.utils.increment_request_count"):
            result = await current_datetime(timezone="America/New_York", format="iso")
            assert "202" in result

    @pytest.mark.asyncio
    async def test_current_datetime_invalid_timezone(self):
        from web_mcp.tools.utils import current_datetime

        with patch("web_mcp.tools.utils.increment_request_count"):
            result = await current_datetime(timezone="Invalid/Zone", format="iso")
            assert "Error" in result

    @pytest.mark.asyncio
    async def test_current_datetime_increments_count(self):
        from web_mcp.tools.utils import current_datetime

        with patch("web_mcp.tools.utils.get_health_metrics") as mock_metrics:
            mock_metrics.return_value = {"status": "healthy", "request_count": 0, "search": {}}

            await current_datetime()

            from web_mcp.tools._core import _request_count

            assert _request_count >= 1


class TestCore:
    def test_increment_request_count(self):
        import web_mcp.tools._core as core

        initial = core._request_count
        core.increment_request_count()
        assert core._request_count == initial + 1

    def test_increment_cache_hits(self):
        import web_mcp.tools._core as core

        initial = core._cache_hits
        core.increment_cache_hits()
        assert core._cache_hits == initial + 1

    def test_get_health_metrics(self):
        from web_mcp.tools._core import get_health_metrics

        with patch("web_mcp.searxng.get_search_metrics") as mock_search:
            mock_search.return_value = {"provider": "searxng", "success_rate": 0.95}
            result = get_health_metrics()

            assert "status" in result
            assert result["status"] == "healthy"
            assert "version" in result
            assert "cache_hit_rate" in result
            assert "request_count" in result
            assert "uptime_seconds" in result
            assert "search" in result

    def test_health_metrics_cache_hit_rate(self):
        # Reset counters
        from web_mcp.tools._core import _cache_hits as ch
        from web_mcp.tools._core import _request_count as rc
        from web_mcp.tools._core import (
            get_health_metrics,
            increment_cache_hits,
            increment_request_count,
        )

        for _ in range(rc):

            import web_mcp.tools._core as core

            core._request_count -= 1
        for _ in range(ch):
            import web_mcp.tools._core as core

            core._cache_hits -= 1

        increment_request_count()
        increment_request_count()
        increment_cache_hits()

        with patch("web_mcp.searxng.get_search_metrics") as mock_search:
            mock_search.return_value = {}
            result = get_health_metrics()
            assert result["request_count"] == 2
            assert result["cache_hit_rate"] > 0

    def test_search_provider_default(self):
        from web_mcp.tools._core import _SEARCH_PROVIDER

        assert _SEARCH_PROVIDER in ("searxng", "brave")

    def test_version(self):
        from web_mcp.tools._core import VERSION

        assert VERSION == "1.0.0"
