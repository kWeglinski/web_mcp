"""Tests for the deduplicate_results function in searxng module."""

from web_mcp.searxng import deduplicate_results


class TestDeduplicateResults:
    """Tests for deduplicate_results function."""

    def test_deduplicate_removes_exact_duplicates(self):
        """Same URL appearing twice should result in one entry."""
        results = [
            {"title": "First", "url": "https://example.com/page", "score": 0.5},
            {"title": "Duplicate", "url": "https://example.com/page", "score": 0.3},
        ]
        output = deduplicate_results(results)

        assert len(output) == 1
        assert output[0]["title"] == "First"

    def test_deduplicate_keeps_highest_scored(self):
        """When same URL appears with different scores, keep the higher one."""
        results = [
            {"title": "Low Score", "url": "https://example.com/page", "score": 0.3},
            {"title": "High Score", "url": "https://example.com/page", "score": 0.9},
        ]
        output = deduplicate_results(results)

        assert len(output) == 1
        assert output[0]["title"] == "High Score"

    def test_deduplicate_preserves_order_of_first_occurrence(self):
        """Order of results should be determined by first occurrence."""
        results = [
            {"title": "Third", "url": "https://example.com/c"},
            {"title": "First", "url": "https://example.com/a"},
            {"title": "Second", "url": "https://example.com/b"},
        ]
        output = deduplicate_results(results)

        titles = [r["title"] for r in output]
        assert titles == ["Third", "First", "Second"]

    def test_deduplicate_handles_empty_urls(self):
        """Results without URLs should be skipped gracefully."""
        results = [
            {"title": "No URL", "url": ""},
            {"title": "Valid", "url": "https://example.com/page"},
            {"title": "Also No URL", "url": None},
        ]
        output = deduplicate_results(results)

        assert len(output) == 1
        assert output[0]["title"] == "Valid"

    def test_deduplicate_no_change_when_all_unique(self):
        """All unique URLs should pass through unchanged."""
        results = [
            {"title": "A", "url": "https://example.com/a", "score": 0.5},
            {"title": "B", "url": "https://example.com/b", "score": 0.7},
            {"title": "C", "url": "https://example.com/c", "score": 0.3},
        ]
        output = deduplicate_results(results)

        assert len(output) == 3
        titles = [r["title"] for r in output]
        assert titles == ["A", "B", "C"]

    def test_deduplicate_uses_bm25_score_when_no_score(self):
        """When score is missing, bm25_score should be used for comparison."""
        results = [
            {"title": "Low BM25", "url": "https://example.com/page", "bm25_score": 10},
            {"title": "High BM25", "url": "https://example.com/page", "bm25_score": 100},
        ]
        output = deduplicate_results(results)

        assert len(output) == 1
        assert output[0]["title"] == "High BM25"

    def test_deduplicate_normalizes_trailing_slashes(self):
        """URLs with and without trailing slashes should be considered duplicates."""
        results = [
            {"title": "No Slash", "url": "https://example.com/page"},
            {"title": "With Slash", "url": "https://example.com/page/", "score": 0.9},
        ]
        output = deduplicate_results(results)

        assert len(output) == 1
        assert output[0]["title"] == "With Slash"

    def test_deduplicate_empty_list(self):
        """Empty list should return empty list."""
        output = deduplicate_results([])
        assert output == []

    def test_deduplicate_single_result(self):
        """Single result should pass through unchanged."""
        results = [{"title": "Only", "url": "https://example.com/page"}]
        output = deduplicate_results(results)

        assert len(output) == 1
        assert output[0]["title"] == "Only"
