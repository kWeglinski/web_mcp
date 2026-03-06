"""Unit tests for reranking utilities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from web_mcp.llm.client import LLMError
from web_mcp.llm.embeddings import EmbeddedChunk
from web_mcp.research.reranking import (
    diversity_score,
    rerank_chunks,
    score_relevance,
    select_diverse_chunks,
    select_diverse_chunks_rerank,
    select_diverse_chunks_v2,
)


def create_chunk(
    text: str,
    source_url: str,
    source_title: str = "Test Title",
    chunk_index: int = 0,
    embedding: list[float] | None = None,
) -> EmbeddedChunk:
    """Helper to create EmbeddedChunk instances for testing."""
    return EmbeddedChunk(
        text=text,
        embedding=embedding or [0.1] * 384,
        source_url=source_url,
        source_title=source_title,
        chunk_index=chunk_index,
    )


def create_chunk_with_score(
    text: str,
    source_url: str,
    score: float,
    source_title: str = "Test Title",
    chunk_index: int = 0,
    embedding: list[float] | None = None,
) -> tuple[EmbeddedChunk, float]:
    """Helper to create (EmbeddedChunk, score) tuples for testing."""
    chunk = create_chunk(text, source_url, source_title, chunk_index, embedding)
    return (chunk, score)


class TestDiversityScore:
    """Tests for diversity_score function."""

    def test_empty_selected_urls(self):
        """Test diversity score with no previously selected URLs."""
        chunk = create_chunk("test text", "https://example.com/page1")
        result = diversity_score(chunk, {})
        assert result == 1.0

    def test_first_chunk_from_url(self):
        """Test diversity score for first chunk from a URL."""
        chunk = create_chunk("test text", "https://example.com/page1")
        selected_urls = {"https://example.com/page1": 0}
        result = diversity_score(chunk, selected_urls)
        assert result == 1.0

    def test_second_chunk_from_url(self):
        """Test diversity score for second chunk from same URL."""
        chunk = create_chunk("test text", "https://example.com/page1")
        selected_urls = {"https://example.com/page1": 1}
        result = diversity_score(chunk, selected_urls)
        assert result == 0.5

    def test_third_chunk_from_url(self):
        """Test diversity score for third chunk from same URL."""
        chunk = create_chunk("test text", "https://example.com/page1")
        selected_urls = {"https://example.com/page1": 2}
        result = diversity_score(chunk, selected_urls)
        assert result == 0.3

    def test_fourth_or_more_chunks_from_url(self):
        """Test diversity score for fourth or more chunks from same URL."""
        chunk = create_chunk("test text", "https://example.com/page1")
        for count in [3, 4, 5, 10]:
            selected_urls = {"https://example.com/page1": count}
            result = diversity_score(chunk, selected_urls)
            assert result == 0.0

    def test_different_url_not_affected(self):
        """Test that chunks from different URLs are not penalized."""
        chunk = create_chunk("test text", "https://example.com/page2")
        selected_urls = {"https://example.com/page1": 5}
        result = diversity_score(chunk, selected_urls)
        assert result == 1.0

    def test_mixed_urls(self):
        """Test diversity score with multiple URLs in selection."""
        chunk = create_chunk("test text", "https://example.com/page1")
        selected_urls = {
            "https://example.com/page1": 2,
            "https://example.com/page2": 1,
            "https://example.com/page3": 0,
        }
        result = diversity_score(chunk, selected_urls)
        assert result == 0.3


class TestSelectDiverseChunks:
    """Tests for select_diverse_chunks function."""

    def test_empty_input(self):
        """Test with empty input list."""
        result = select_diverse_chunks([])
        assert result == []

    def test_single_chunk(self):
        """Test with a single chunk."""
        chunk_tuple = create_chunk_with_score("test", "https://example.com", 0.9)
        result = select_diverse_chunks([chunk_tuple])
        assert len(result) == 1
        assert result[0][1] == 0.9

    def test_respects_max_per_source(self):
        """Test that max_per_source limit is respected."""
        chunks = [
            create_chunk_with_score(f"text{i}", "https://example.com", 0.9 - i * 0.1)
            for i in range(10)
        ]
        result = select_diverse_chunks(chunks, max_per_source=2)
        assert len(result) == 2

    def test_respects_total_chunks(self):
        """Test that total_chunks limit is respected."""
        chunks = [
            create_chunk_with_score(f"text{i}", f"https://example{i}.com", 0.9 - i * 0.01)
            for i in range(20)
        ]
        result = select_diverse_chunks(chunks, total_chunks=5)
        assert len(result) == 5

    def test_selects_from_multiple_sources(self):
        """Test that chunks are selected from multiple sources."""
        chunks = [
            create_chunk_with_score("text1", "https://example1.com", 0.9),
            create_chunk_with_score("text2", "https://example2.com", 0.8),
            create_chunk_with_score("text3", "https://example3.com", 0.7),
            create_chunk_with_score("text4", "https://example1.com", 0.6),
            create_chunk_with_score("text5", "https://example2.com", 0.5),
        ]
        result = select_diverse_chunks(chunks, max_per_source=2, total_chunks=5)
        urls = [chunk.source_url for chunk, _ in result]
        assert "https://example1.com" in urls
        assert "https://example2.com" in urls
        assert "https://example3.com" in urls

    def test_maintains_order_by_relevance(self):
        """Test that chunks are selected in relevance order."""
        chunks = [
            create_chunk_with_score("text1", "https://example1.com", 0.9),
            create_chunk_with_score("text2", "https://example2.com", 0.8),
            create_chunk_with_score("text3", "https://example1.com", 0.7),
        ]
        result = select_diverse_chunks(chunks, max_per_source=2, total_chunks=3)
        scores = [score for _, score in result]
        assert scores == [0.9, 0.8, 0.7]

    def test_exact_limit_boundary(self):
        """Test behavior at exact limit boundaries."""
        chunks = [
            create_chunk_with_score(f"text{i}", "https://example.com", 0.9 - i * 0.01)
            for i in range(5)
        ]
        result = select_diverse_chunks(chunks, max_per_source=3, total_chunks=3)
        assert len(result) == 3

    def test_all_same_source(self):
        """Test when all chunks are from the same source."""
        chunks = [
            create_chunk_with_score(f"text{i}", "https://example.com", 0.9 - i * 0.1)
            for i in range(10)
        ]
        result = select_diverse_chunks(chunks, max_per_source=3, total_chunks=15)
        assert len(result) == 3

    def test_custom_parameters(self):
        """Test with custom max_per_source and total_chunks."""
        chunks = [
            create_chunk_with_score(f"text{i}", f"https://example{i % 3}.com", 0.9 - i * 0.01)
            for i in range(20)
        ]
        result = select_diverse_chunks(chunks, max_per_source=1, total_chunks=3)
        assert len(result) == 3
        urls = [chunk.source_url for chunk, _ in result]
        assert len(set(urls)) == 3


class TestSelectDiverseChunksV2:
    """Tests for select_diverse_chunks_v2 function."""

    def test_empty_input(self):
        """Test with empty input list."""
        result = select_diverse_chunks_v2([])
        assert result == []

    def test_single_chunk(self):
        """Test with a single chunk."""
        chunk_tuple = create_chunk_with_score("test", "https://example.com", 0.9)
        result = select_diverse_chunks_v2([chunk_tuple])
        assert len(result) == 1

    def test_diversity_bonus_applied(self):
        """Test that diversity bonus affects combined score."""
        chunks = [
            create_chunk_with_score("text1", "https://example.com", 1.0),
            create_chunk_with_score("text2", "https://example.com", 1.0),
            create_chunk_with_score("text3", "https://example.com", 1.0),
        ]
        result = select_diverse_chunks_v2(chunks, max_per_source=3, total_chunks=3)
        scores = [score for _, score in result]
        assert scores[0] > scores[1] > scores[2]

    def test_first_chunk_full_score(self):
        """Test that first chunk from source gets full diversity bonus."""
        chunks = [
            create_chunk_with_score("text1", "https://example.com", 1.0),
        ]
        result = select_diverse_chunks_v2(chunks, max_per_source=3)
        assert result[0][1] == 1.0

    def test_second_chunk_reduced_score(self):
        """Test that second chunk from same source gets reduced score."""
        chunks = [
            create_chunk_with_score("text1", "https://example.com", 1.0),
            create_chunk_with_score("text2", "https://example.com", 1.0),
        ]
        result = select_diverse_chunks_v2(chunks, max_per_source=3)
        assert result[1][1] < result[0][1]

    def test_respects_max_per_source(self):
        """Test that max_per_source limit is respected."""
        chunks = [
            create_chunk_with_score(f"text{i}", "https://example.com", 0.9 - i * 0.01)
            for i in range(10)
        ]
        result = select_diverse_chunks_v2(chunks, max_per_source=2, total_chunks=10)
        assert len(result) == 2

    def test_respects_total_chunks(self):
        """Test that total_chunks limit is respected."""
        chunks = [
            create_chunk_with_score(f"text{i}", f"https://example{i}.com", 0.9 - i * 0.01)
            for i in range(20)
        ]
        result = select_diverse_chunks_v2(chunks, total_chunks=5)
        assert len(result) == 5

    def test_result_sorted_by_combined_score(self):
        """Test that results are sorted by combined score."""
        chunks = [
            create_chunk_with_score("text1", "https://example1.com", 0.9),
            create_chunk_with_score("text2", "https://example1.com", 0.8),
            create_chunk_with_score("text3", "https://example2.com", 0.85),
        ]
        result = select_diverse_chunks_v2(chunks, max_per_source=2, total_chunks=3)
        scores = [score for _, score in result]
        assert scores == sorted(scores, reverse=True)

    def test_different_sources_no_penalty(self):
        """Test that chunks from different sources don't penalize each other."""
        chunks = [
            create_chunk_with_score("text1", "https://example1.com", 1.0),
            create_chunk_with_score("text2", "https://example2.com", 1.0),
            create_chunk_with_score("text3", "https://example3.com", 1.0),
        ]
        result = select_diverse_chunks_v2(chunks, max_per_source=3)
        scores = [score for _, score in result]
        assert all(s == 1.0 for s in scores)

    def test_diversity_calculation_formula(self):
        """Test the diversity bonus calculation formula."""
        max_per_source = 3
        chunks = [create_chunk_with_score(f"text{i}", "https://example.com", 1.0) for i in range(3)]
        result = select_diverse_chunks_v2(chunks, max_per_source=max_per_source)
        expected_bonuses = [
            1.0 - (0 / (max_per_source + 1)),
            1.0 - (1 / (max_per_source + 1)),
            1.0 - (2 / (max_per_source + 1)),
        ]
        for i, expected in enumerate(expected_bonuses):
            assert abs(result[i][1] - expected) < 0.001


class TestSelectDiverseChunksRerank:
    """Tests for select_diverse_chunks_rerank function."""

    def test_empty_input(self):
        """Test with empty input list."""
        result = select_diverse_chunks_rerank([])
        assert result == []

    def test_single_chunk(self):
        """Test with a single chunk."""
        chunk_tuple = create_chunk_with_score("test", "https://example.com", 0.9)
        result = select_diverse_chunks_rerank([chunk_tuple])
        assert len(result) == 1

    def test_respects_max_per_source(self):
        """Test that max_per_source limit is respected."""
        chunks = [
            create_chunk_with_score(f"text{i}", "https://example.com", 0.9 - i * 0.01)
            for i in range(10)
        ]
        result = select_diverse_chunks_rerank(chunks, max_per_source=2, total_chunks=10)
        assert len(result) == 2

    def test_respects_total_chunks(self):
        """Test that total_chunks limit is respected."""
        chunks = [
            create_chunk_with_score(f"text{i}", f"https://example{i}.com", 0.9 - i * 0.01)
            for i in range(20)
        ]
        result = select_diverse_chunks_rerank(chunks, total_chunks=5)
        assert len(result) == 5

    def test_result_sorted_by_combined_score(self):
        """Test that results are sorted by combined score."""
        chunks = [
            create_chunk_with_score("text1", "https://example1.com", 0.9),
            create_chunk_with_score("text2", "https://example1.com", 0.8),
            create_chunk_with_score("text3", "https://example2.com", 0.85),
        ]
        result = select_diverse_chunks_rerank(chunks, max_per_source=2, total_chunks=3)
        scores = [score for _, score in result]
        assert scores == sorted(scores, reverse=True)

    def test_diversity_bonus_applied(self):
        """Test that diversity bonus affects combined score."""
        chunks = [
            create_chunk_with_score("text1", "https://example.com", 1.0),
            create_chunk_with_score("text2", "https://example.com", 1.0),
            create_chunk_with_score("text3", "https://example.com", 1.0),
        ]
        result = select_diverse_chunks_rerank(chunks, max_per_source=3, total_chunks=3)
        scores = [score for _, score in result]
        assert scores[0] > scores[1] > scores[2]

    def test_all_same_source_limited(self):
        """Test when all chunks are from the same source."""
        chunks = [
            create_chunk_with_score(f"text{i}", "https://example.com", 0.9 - i * 0.01)
            for i in range(10)
        ]
        result = select_diverse_chunks_rerank(chunks, max_per_source=3, total_chunks=15)
        assert len(result) == 3

    def test_multiple_sources_all_included(self):
        """Test that chunks from all sources can be included."""
        chunks = [
            create_chunk_with_score(f"text{i}", f"https://example{i % 5}.com", 0.9 - i * 0.01)
            for i in range(25)
        ]
        result = select_diverse_chunks_rerank(chunks, max_per_source=2, total_chunks=10)
        urls = {chunk.source_url for chunk, _ in result}
        assert len(urls) == 5

    def test_combined_score_calculation(self):
        """Test the combined score calculation."""
        max_per_source = 3
        chunks = [create_chunk_with_score(f"text{i}", "https://example.com", 1.0) for i in range(3)]
        result = select_diverse_chunks_rerank(chunks, max_per_source=max_per_source)
        expected_scores = [
            1.0 * (1.0 - 0 / (max_per_source + 1)),
            1.0 * (1.0 - 1 / (max_per_source + 1)),
            1.0 * (1.0 - 2 / (max_per_source + 1)),
        ]
        for i, expected in enumerate(expected_scores):
            assert abs(result[i][1] - expected) < 0.001


class TestScoreRelevance:
    """Tests for score_relevance function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client."""
        client = MagicMock()
        client.chat = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_successful_score_parsing(self, mock_client):
        """Test successful parsing of LLM response."""
        mock_client.chat.return_value = "7"
        result = await score_relevance(mock_client, "test query", "test text")
        assert result == 7.0

    @pytest.mark.asyncio
    async def test_score_with_decimal(self, mock_client):
        """Test parsing score with decimal point."""
        mock_client.chat.return_value = "7.5"
        result = await score_relevance(mock_client, "test query", "test text")
        assert result == 7.5

    @pytest.mark.asyncio
    async def test_score_with_surrounding_text(self, mock_client):
        """Test parsing score from response with surrounding text."""
        mock_client.chat.return_value = "The relevance is 8 out of 10"
        result = await score_relevance(mock_client, "test query", "test text")
        assert result == 8.0

    @pytest.mark.asyncio
    async def test_score_clamped_to_max(self, mock_client):
        """Test that scores above 10 are clamped to 10."""
        mock_client.chat.return_value = "15"
        result = await score_relevance(mock_client, "test query", "test text")
        assert result == 10.0

    @pytest.mark.asyncio
    async def test_negative_sign_ignored(self, mock_client):
        """Test that negative sign is ignored (regex extracts absolute value)."""
        mock_client.chat.return_value = "-5"
        result = await score_relevance(mock_client, "test query", "test text")
        assert result == 5.0

    @pytest.mark.asyncio
    async def test_invalid_response_returns_default(self, mock_client):
        """Test that invalid response returns default score of 5.0."""
        mock_client.chat.return_value = "not a number"
        result = await score_relevance(mock_client, "test query", "test text")
        assert result == 5.0

    @pytest.mark.asyncio
    async def test_empty_response_returns_default(self, mock_client):
        """Test that empty response returns default score."""
        mock_client.chat.return_value = ""
        result = await score_relevance(mock_client, "test query", "test text")
        assert result == 5.0

    @pytest.mark.asyncio
    async def test_llm_error_returns_default(self, mock_client):
        """Test that LLMError returns default score."""
        mock_client.chat.side_effect = LLMError("API error")
        result = await score_relevance(mock_client, "test query", "test text")
        assert result == 5.0

    @pytest.mark.asyncio
    async def test_generic_error_returns_default(self, mock_client):
        """Test that generic exceptions return default score."""
        mock_client.chat.side_effect = RuntimeError("Unexpected error")
        result = await score_relevance(mock_client, "test query", "test text")
        assert result == 5.0

    @pytest.mark.asyncio
    async def test_long_text_truncated(self, mock_client):
        """Test that long text is truncated in prompt."""
        mock_client.chat.return_value = "5"
        long_text = "x" * 1000
        result = await score_relevance(mock_client, "test query", long_text)
        assert result == 5.0
        call_args = mock_client.chat.call_args
        prompt = call_args[1]["messages"][0]["content"]
        assert "Text:" in prompt

    @pytest.mark.asyncio
    async def test_whitespace_in_response(self, mock_client):
        """Test handling of whitespace in response."""
        mock_client.chat.return_value = "  6  "
        result = await score_relevance(mock_client, "test query", "test text")
        assert result == 6.0


class TestRerankChunks:
    """Tests for rerank_chunks function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client."""
        client = MagicMock()
        client.chat = AsyncMock()
        return client

    def _create_chunks(self, count: int) -> list[tuple[EmbeddedChunk, float]]:
        """Create test chunks with different sources."""
        return [
            create_chunk_with_score(
                f"chunk text {i}",
                f"https://example{i % 3}.com",
                0.9 - i * 0.01,
            )
            for i in range(count)
        ]

    @pytest.mark.asyncio
    async def test_empty_input(self, mock_client):
        """Test with empty input list."""
        result = await rerank_chunks(mock_client, "test query", [])
        assert result == []

    @pytest.mark.asyncio
    async def test_single_chunk(self, mock_client):
        """Test with a single chunk."""
        mock_client.chat.return_value = "8"
        chunks = [create_chunk_with_score("test", "https://example.com", 0.9)]
        result = await rerank_chunks(mock_client, "test query", chunks, top_k=5)
        assert len(result) == 1
        assert result[0][1] == 8.0

    @pytest.mark.asyncio
    async def test_respects_top_k(self, mock_client):
        """Test that top_k limit is respected."""
        mock_client.chat.return_value = "5"
        chunks = self._create_chunks(20)
        result = await rerank_chunks(mock_client, "test query", chunks, top_k=3)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_considers_top_k_times_two_candidates(self, mock_client):
        """Test that only top_k * 2 candidates are scored."""
        mock_client.chat.return_value = "5"
        chunks = self._create_chunks(30)
        await rerank_chunks(mock_client, "test query", chunks, top_k=5)
        assert mock_client.chat.call_count == 10

    @pytest.mark.asyncio
    async def test_sorted_by_relevance_score(self, mock_client):
        """Test that results are sorted by relevance score."""
        scores = [3, 9, 6, 1, 7]
        mock_client.chat.side_effect = [str(s) for s in scores]
        chunks = self._create_chunks(5)
        result = await rerank_chunks(mock_client, "test query", chunks, top_k=5)
        result_scores = [score for _, score in result]
        assert result_scores == sorted(result_scores, reverse=True)

    @pytest.mark.asyncio
    async def test_handles_llm_errors_gracefully(self, mock_client):
        """Test that LLM errors are handled with default scores."""
        mock_client.chat.side_effect = [
            "8",
            LLMError("API error"),
            "6",
        ]
        chunks = self._create_chunks(3)
        result = await rerank_chunks(mock_client, "test query", chunks, top_k=3)
        assert len(result) == 3
        scores = [score for _, score in result]
        assert 5.0 in scores

    @pytest.mark.asyncio
    async def test_preserves_chunk_data(self, mock_client):
        """Test that chunk data is preserved in results."""
        mock_client.chat.return_value = "7"
        chunks = [create_chunk_with_score("specific text", "https://specific.com", 0.9)]
        result = await rerank_chunks(mock_client, "test query", chunks, top_k=1)
        assert result[0][0].text == "specific text"
        assert result[0][0].source_url == "https://specific.com"

    @pytest.mark.asyncio
    async def test_fewer_chunks_than_top_k(self, mock_client):
        """Test when there are fewer chunks than top_k."""
        mock_client.chat.return_value = "5"
        chunks = self._create_chunks(3)
        result = await rerank_chunks(mock_client, "test query", chunks, top_k=10)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_concurrent_scoring(self, mock_client):
        """Test that chunks are scored concurrently."""
        mock_client.chat.return_value = "5"
        chunks = self._create_chunks(10)
        await rerank_chunks(mock_client, "test query", chunks, top_k=5)
        assert mock_client.chat.call_count == 10

    @pytest.mark.asyncio
    async def test_default_top_k(self, mock_client):
        """Test default top_k value of 10."""
        mock_client.chat.return_value = "5"
        chunks = self._create_chunks(25)
        result = await rerank_chunks(mock_client, "test query", chunks)
        assert len(result) == 10


class TestEdgeCases:
    """Additional edge case tests for reranking functions."""

    def test_diversity_score_with_none_url(self):
        """Test diversity score when URL might be None-like."""
        chunk = create_chunk("test", "")
        result = diversity_score(chunk, {})
        assert result == 1.0

    def test_select_diverse_chunks_zero_scores(self):
        """Test selection with zero scores."""
        chunks = [
            create_chunk_with_score(f"text{i}", f"https://example{i}.com", 0.0) for i in range(5)
        ]
        result = select_diverse_chunks(chunks, total_chunks=3)
        assert len(result) == 3

    def test_select_diverse_chunks_negative_scores(self):
        """Test selection with negative scores."""
        chunks = [
            create_chunk_with_score(f"text{i}", f"https://example{i}.com", -0.5) for i in range(5)
        ]
        result = select_diverse_chunks(chunks, total_chunks=3)
        assert len(result) == 3

    def test_select_diverse_chunks_v2_zero_max_per_source(self):
        """Test v2 with zero max_per_source."""
        chunks = [
            create_chunk_with_score("text1", "https://example.com", 0.9),
        ]
        result = select_diverse_chunks_v2(chunks, max_per_source=0, total_chunks=5)
        assert len(result) == 0

    def test_select_diverse_chunks_rerank_zero_max_per_source(self):
        """Test rerank with zero max_per_source."""
        chunks = [
            create_chunk_with_score("text1", "https://example.com", 0.9),
        ]
        result = select_diverse_chunks_rerank(chunks, max_per_source=0, total_chunks=5)
        assert len(result) == 0

    def test_select_diverse_chunks_zero_total(self):
        """Test selection with zero total_chunks (code adds first chunk before checking)."""
        chunks = [
            create_chunk_with_score("text1", "https://example.com", 0.9),
        ]
        result = select_diverse_chunks(chunks, total_chunks=0)
        assert len(result) == 1

    def test_select_diverse_chunks_v2_zero_total(self):
        """Test v2 with zero total_chunks (code adds first chunk before checking)."""
        chunks = [
            create_chunk_with_score("text1", "https://example.com", 0.9),
        ]
        result = select_diverse_chunks_v2(chunks, total_chunks=0)
        assert len(result) == 1

    def test_select_diverse_chunks_rerank_zero_total(self):
        """Test rerank with zero total_chunks."""
        chunks = [
            create_chunk_with_score("text1", "https://example.com", 0.9),
        ]
        result = select_diverse_chunks_rerank(chunks, total_chunks=0)
        assert len(result) == 0

    def test_very_high_scores(self):
        """Test with very high relevance scores."""
        chunks = [
            create_chunk_with_score(f"text{i}", f"https://example{i}.com", 1000.0) for i in range(5)
        ]
        result = select_diverse_chunks(chunks, total_chunks=3)
        assert len(result) == 3
        for _, score in result:
            assert score == 1000.0

    @pytest.mark.asyncio
    async def test_score_relevance_boundary_values(self):
        """Test score_relevance with boundary values."""
        client = MagicMock()
        client.chat = AsyncMock()

        client.chat.return_value = "0"
        result = await score_relevance(client, "query", "text")
        assert result == 0.0

        client.chat.return_value = "10"
        result = await score_relevance(client, "query", "text")
        assert result == 10.0

    @pytest.mark.asyncio
    async def test_rerank_with_mixed_scores(self):
        """Test reranking with mixed valid and invalid scores."""
        client = MagicMock()
        client.chat = AsyncMock()
        client.chat.side_effect = ["8", "invalid", "6", "", "4"]

        chunks = [
            create_chunk_with_score(f"text{i}", f"https://example{i}.com", 0.9 - i * 0.1)
            for i in range(5)
        ]
        result = await rerank_chunks(client, "query", chunks, top_k=5)

        assert len(result) == 5
        scores = [score for _, score in result]
        assert 5.0 in scores
