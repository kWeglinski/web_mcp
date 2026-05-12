"""Tests for search analytics / metrics tracking (improvement #11)."""

import pytest


@pytest.fixture(autouse=True)
def _reset_metrics():
    from web_mcp.searxng import reset_search_metrics

    reset_search_metrics()
    yield
    reset_search_metrics()


def test_record_search_tracks_provider_success():
    from web_mcp.searxng import _record_search, get_search_metrics

    _record_search("searxng", True, 150.0)
    metrics = get_search_metrics()

    assert metrics["total_queries"] == 1
    assert metrics["provider_success_rates"]["searxng"] == 1.0
    assert "brave" not in metrics["provider_success_rates"]


def test_record_search_tracks_failure():
    from web_mcp.searxng import _record_search, get_search_metrics

    _record_search("searxng", False, 200.0)
    metrics = get_search_metrics()

    assert metrics["total_queries"] == 1
    assert metrics["provider_failures"]["searxng"] == 1
    assert "searxng" not in metrics["provider_success_rates"]


def test_get_metrics_returns_all_fields():
    from web_mcp.searxng import _record_search, get_search_metrics

    _record_search("searxng", True, 100.0)
    _record_search("searxng", True, 200.0)
    _record_search("searxng", False, 50.0)

    metrics = get_search_metrics()

    assert "total_queries" in metrics
    assert "cache_hit_rate" in metrics
    assert "provider_success_rates" in metrics
    assert "provider_failures" in metrics
    assert "avg_latency_ms" in metrics

    assert metrics["total_queries"] == 3
    assert metrics["cache_hit_rate"] == 0.0
    assert metrics["provider_success_rates"]["searxng"] == round(2 / 3, 3)
    assert metrics["provider_failures"]["searxng"] == 1
    assert metrics["avg_latency_ms"] == 116.7


def test_search_analytics_in_health_endpoint():
    from web_mcp.searxng import _record_search

    _record_search("searxng", True, 100.0)

    from web_mcp.tools._core import get_health_metrics

    health = get_health_metrics()
    assert "search" in health
    assert health["search"]["total_queries"] == 1
    assert "provider_success_rates" in health["search"]
