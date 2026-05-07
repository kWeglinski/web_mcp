"""Tests for smarter instance selection for SearXNG fallbacks (improvement #12)."""


def test_get_instance_score_unknown_returns_neutral():
    from web_mcp.searxng import _get_instance_score, reset_instance_stats

    reset_instance_stats()
    score = _get_instance_score("https://unknown.example.com")
    assert score == 1.0


def test_get_instance_score_high_success_rate():
    from web_mcp.searxng import InstanceStats, _get_instance_score, _instance_stats

    stats = InstanceStats(
        url="https://fast.example.com",
        success_count=9,
        failure_count=1,
        total_latency_ms=3000.0,
    )
    _instance_stats["https://fast.example.com"] = stats

    score = _get_instance_score("https://fast.example.com")
    assert score > 0.8


def test_get_instance_score_slow_penalized():
    from web_mcp.searxng import InstanceStats, _get_instance_score, _instance_stats

    fast_stats = InstanceStats(
        url="https://fast.example.com",
        success_count=5,
        failure_count=0,
        total_latency_ms=2500.0,
    )

    slow_stats = InstanceStats(
        url="https://slow.example.com",
        success_count=5,
        failure_count=0,
        total_latency_ms=17500.0,
    )

    _instance_stats["https://fast.example.com"] = fast_stats
    _instance_stats["https://slow.example.com"] = slow_stats

    fast_score = _get_instance_score("https://fast.example.com")
    slow_score = _get_instance_score("https://slow.example.com")

    assert fast_score > slow_score


def test_instance_stats_recorded_after_use():
    from web_mcp.searxng import (
        _instance_stats,
        _record_instance_result,
        reset_instance_stats,
    )

    reset_instance_stats()

    _record_instance_result("https://example.com", True, 150.0)
    _record_instance_result("https://example.com", True, 200.0)
    _record_instance_result("https://example.com", False, 500.0)

    stats = _instance_stats["https://example.com"]
    assert stats.success_count == 2
    assert stats.failure_count == 1
    assert stats.total_latency_ms == 850.0
