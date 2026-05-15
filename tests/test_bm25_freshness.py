"""Tests for BM25 content freshness scoring."""

from datetime import UTC, datetime, timedelta

from web_mcp.research.bm25 import (
    _freshness_score,
    _parse_result_date,
    rerank_search_results,
)

NOW = datetime(2026, 5, 7, 12, 0, 0, tzinfo=UTC)


def _future_dt(days: int) -> str:
    """Return an ISO date string `days` in the future."""
    dt = datetime(2026, 5, 7, 12, 0, 0) + timedelta(days=days)
    return dt.isoformat()


def _past_dt(days: int) -> str:
    """Return an ISO date string `days` in the past."""
    dt = datetime(2026, 5, 7, 12, 0, 0) - timedelta(days=days)
    return dt.isoformat()


class TestParseResultDate:
    def test_parses_published_date(self):
        result = {"published_date": "2026-05-01T10:30:00Z"}
        dt = _parse_result_date(result)
        assert dt == datetime(2026, 5, 1, 10, 30, 0, tzinfo=UTC)

    def test_parses_published_date_field(self):
        result = {"publishedDate": "2026-04-15T08:00:00+00:00"}
        dt = _parse_result_date(result)
        assert dt == datetime(2026, 4, 15, 8, 0, 0, tzinfo=UTC)

    def test_parses_date_field(self):
        result = {"date": "2026-03-01"}
        dt = _parse_result_date(result)
        assert dt == datetime(2026, 3, 1)

    def test_parses_pubdate(self):
        result = {"pubdate": "2026-01-15T14:00:00"}
        dt = _parse_result_date(result)
        assert dt == datetime(2026, 1, 15, 14, 0, 0)

    def test_returns_none_when_no_date_field(self):
        result = {"title": "no date here"}
        assert _parse_result_date(result) is None

    def test_returns_none_for_invalid_date(self):
        result = {"date": "not-a-date"}
        assert _parse_result_date(result) is None

    def test_prefers_first_valid_field(self):
        result = {"published_date": "invalid", "date": "2026-05-01"}
        dt = _parse_result_date(result)
        assert dt == datetime(2026, 5, 1)


class TestFreshnessScore:
    def test_recent_result_today(self):
        result = {"published_date": _past_dt(0)}
        score = _freshness_score(result, now=NOW)
        assert 0.95 <= score <= 1.0

    def test_recent_result_within_24h(self):
        result = {"published_date": _past_dt(0)}
        score = _freshness_score(result, now=NOW)
        assert 0.95 <= score <= 1.0

    def test_result_3_days_old(self):
        result = {"published_date": _past_dt(3)}
        score = _freshness_score(result, now=NOW)
        assert 0.75 <= score <= 0.85

    def test_result_10_days_old(self):
        result = {"published_date": _past_dt(10)}
        score = _freshness_score(result, now=NOW)
        assert 0.45 <= score <= 0.55

    def test_result_60_days_old(self):
        result = {"published_date": _past_dt(60)}
        score = _freshness_score(result, now=NOW)
        assert 0.15 <= score <= 0.25

    def test_unknown_date_neutral(self):
        result = {"title": "no date"}
        score = _freshness_score(result, now=NOW)
        assert score == 0.5


class TestRerankFreshness:
    def _make_results(self):
        return [
            {
                "title": "Latest AI breakthrough 2026",
                "snippet": "A new development in artificial intelligence.",
                "published_date": _past_dt(1),
            },
            {
                "title": "AI Research from 2023",
                "snippet": "Old research paper on neural networks.",
                "published_date": _past_dt(90),
            },
            {
                "title": "News about AI today",
                "snippet": "Breaking news in the AI space.",
            },
        ]

    def test_combined_score_is_weighted_mix(self):
        results = self._make_results()
        ranked = rerank_search_results(results, "AI", freshness_weight=0.2)

        assert all("combined_score" in r for r in ranked)
        assert all("bm25_score" in r for r in ranked)

        scores = [r["combined_score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_rerank_zero_freshweight_equals_bm25_only(self):
        results = self._make_results()

        rerank_search_results(results, "AI", freshness_weight=0.2)

        ranked_no_freshness = rerank_search_results(results, "AI", freshness_weight=0.0)

        assert all("combined_score" not in r for r in ranked_no_freshness)
        bm25_scores = [r["bm25_score"] for r in ranked_no_freshness]
        assert bm25_scores == sorted(bm25_scores, reverse=True)

    def test_rerank_no_dates_unchanged(self):
        results_no_dates = [
            {"title": "Result A", "snippet": "Some text about ai"},
            {"title": "Result B", "snippet": "More ai content here"},
        ]

        ranked = rerank_search_results(results_no_dates, "ai", freshness_weight=0.3)

        assert all("combined_score" not in r for r in ranked)
        assert all("bm25_score" in r for r in ranked)

    def test_empty_results(self):
        assert rerank_search_results([], "test") == []

    def test_empty_query(self):
        assert rerank_search_results([{"title": "a"}], "") == [{"title": "a"}]
