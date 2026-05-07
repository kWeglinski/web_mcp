"""Tests for multi-query parallel search in research pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_llm_config():
    """Mock LLM config as configured."""
    with patch("web_mcp.research.pipeline.get_llm_config") as mock:
        config = MagicMock()
        config.is_configured = True
        mock.return_value = config
        yield config


@pytest.fixture
def mock_research_config():
    """Mock research config with rewrite enabled."""
    with patch("web_mcp.research.pipeline.get_research_config") as mock:
        config = MagicMock()
        config.rewrite_enabled = True
        config.search_results = 10
        config.chunk_size = 1000
        config.chunk_overlap = 200
        config.top_chunks = 10
        mock.return_value = config
        yield config


@pytest.fixture
def mock_llm_client():
    """Mock LLM client."""
    with patch("web_mcp.research.pipeline.get_llm_client") as mock:
        client = MagicMock()
        client.chat = AsyncMock(return_value="optimized search query")
        mock.return_value = client
        yield client


@pytest.fixture
def mock_rewrite_query():
    """Mock rewrite_query to return a rewritten query."""
    with patch("web_mcp.research.pipeline.rewrite_query") as mock:
        mock.return_value = "optimized search query"
        yield mock


@pytest.fixture
def mock_generate_sub_queries():
    """Mock generate_sub_queries to return multiple sub-queries."""
    with patch("web_mcp.research.pipeline.generate_sub_queries") as mock:
        mock.return_value = [
            "React components tutorial",
            "Vue.js getting started guide",
            "React vs Vue comparison",
        ]
        yield mock


@pytest.fixture
def mock_search():
    """Mock search to return sample results."""
    with patch("web_mcp.research.pipeline.search") as mock:

        def side_effect(query, max_results):
            return [
                {
                    "title": f"Result for {query}",
                    "url": f"https://example.com/{query.replace(' ', '-')}",
                    "snippet": f"Snippet for {query}",
                    "score": 0.9,
                }
            ]

        mock.side_effect = side_effect
        yield mock


@pytest.fixture
def mock_fetch_and_extract():
    """Mock _fetch_and_extract to return valid content."""
    with patch("web_mcp.research.pipeline._fetch_and_extract") as mock:
        mock.return_value = MagicMock(
            url="https://example.com/test",
            title="Test",
            text="This is test content for extraction.",
            error=None,
        )
        yield mock


@pytest.fixture
def mock_chunker():
    """Mock chunk_text and merge_small_chunks."""
    with patch("web_mcp.research.pipeline.chunk_text") as mock_chunk:
        with patch("web_mcp.research.pipeline.merge_small_chunks") as mock_merge:
            mock_chunk.return_value = [
                MagicMock(
                    text="chunk text",
                    source_url="https://example.com/test",
                    source_title="Test",
                    index=0,
                )
            ]
            mock_merge.return_value = [
                MagicMock(
                    text="chunk text",
                    source_url="https://example.com/test",
                    source_title="Test",
                    index=0,
                )
            ]
            yield mock_chunk, mock_merge


@pytest.fixture
def mock_embeddings():
    """Mock embedding functions."""
    with patch("web_mcp.research.pipeline.embed_chunks") as mock_embed:
        with patch("web_mcp.research.pipeline.embed_query") as mock_qembed:
            with patch("web_mcp.research.pipeline.find_most_relevant") as mock_find:
                mock_qembed.return_value = [0.1] * 384
                mock_embed.return_value = [[0.2] * 384]
                mock_find.return_value = [("chunk text", "https://example.com/test", "Test", 0)]
                yield mock_find


@pytest.fixture
def mock_reranking():
    """Mock reranking functions."""
    with patch("web_mcp.research.pipeline.rerank_chunks") as mock_rerank:
        with patch("web_mcp.research.pipeline.select_diverse_chunks_v2") as mock_select:
            mock_rerank.side_effect = lambda *a, **k: [
                ("chunk text", "https://example.com/test", "Test", 0)
            ]
            mock_select.return_value = [("chunk text", "https://example.com/test", "Test", 0)]
            yield mock_select


@pytest.fixture
def mock_citations():
    """Mock citation building."""
    with patch("web_mcp.research.pipeline.build_context_with_citations") as mock_ctx:
        with patch("web_mcp.research.pipeline.validate_citations") as mock_val:
            mock_ctx.return_value = (
                "context",
                [{"url": "https://example.com/test", "title": "Test"}],
            )
            mock_val.return_value = {"valid": True}
            yield mock_ctx


@pytest.fixture
def mock_llm_chat():
    """Mock LLM chat for final answer generation."""
    with patch("web_mcp.research.pipeline.get_llm_client") as mock:
        client = MagicMock()
        client.chat = AsyncMock(return_value="This is the researched answer.")
        mock.return_value = client
        yield client


class TestMultiQuerySearch:
    """Tests for parallel sub-query search execution."""

    async def test_research_uses_single_search_for_simple_queries(
        self,
        mock_llm_config,
        mock_research_config,
        mock_search,
        mock_rewrite_query,
        mock_generate_sub_queries,
        mock_fetch_and_extract,
        mock_chunker,
        mock_embeddings,
        mock_reranking,
        mock_citations,
        mock_llm_chat,
    ):
        """When generate_sub_queries returns only 1 query, use single search."""
        mock_generate_sub_queries.return_value = ["original query"]

        from web_mcp.research.pipeline import research

        await research("What is Python?")

        assert mock_search.call_count == 1
        mock_generate_sub_queries.assert_called_once()

    async def test_research_parallelizes_sub_queries(
        self,
        mock_llm_config,
        mock_research_config,
        mock_search,
        mock_rewrite_query,
        mock_generate_sub_queries,
        mock_fetch_and_extract,
        mock_chunker,
        mock_embeddings,
        mock_reranking,
        mock_citations,
        mock_llm_chat,
    ):
        """When generate_sub_queries returns 3 queries, make 3 parallel search calls."""
        mock_generate_sub_queries.return_value = [
            "React components tutorial",
            "Vue.js getting started guide",
            "React vs Vue comparison",
        ]

        from web_mcp.research.pipeline import research

        await research("Compare React and Vue")

        assert mock_search.call_count == 3
        search_calls = {call[0][0] for call in mock_search.call_args_list}
        assert "React components tutorial" in search_calls
        assert "Vue.js getting started guide" in search_calls
        assert "React vs Vue comparison" in search_calls

    async def test_research_handles_partial_failure(
        self,
        mock_llm_config,
        mock_research_config,
        mock_search,
        mock_rewrite_query,
        mock_generate_sub_queries,
        mock_fetch_and_extract,
        mock_chunker,
        mock_embeddings,
        mock_reranking,
        mock_citations,
        mock_llm_chat,
    ):
        """When 1 of 3 sub-query searches fails, others still succeed."""
        from web_mcp.searxng import SearXNGError

        mock_generate_sub_queries.return_value = [
            "React components tutorial",
            "Vue.js getting started guide",
            "React vs Vue comparison",
        ]

        call_count = 0

        def search_side_effect(query, max_results):
            nonlocal call_count
            call_count += 1
            if "Vue" in query:
                raise SearXNGError("Service unavailable", 503)
            return [
                {
                    "title": f"Result for {query}",
                    "url": f"https://example.com/{query.replace(' ', '-')}",
                    "snippet": f"Snippet for {query}",
                    "score": 0.9,
                }
            ]

        mock_search.side_effect = search_side_effect

        from web_mcp.research.pipeline import research

        result = await research("Compare React and Vue")

        assert mock_search.call_count == 3
        assert result.answer == "This is the researched answer."

    async def test_research_skips_parallel_when_rewrite_disabled(
        self,
        mock_llm_config,
        mock_search,
        mock_generate_sub_queries,
        mock_fetch_and_extract,
        mock_chunker,
        mock_embeddings,
        mock_reranking,
        mock_citations,
        mock_llm_chat,
    ):
        """When rewrite_enabled is False, use single search even with sub-queries."""
        from unittest.mock import patch

        mock_research_config = MagicMock()
        mock_research_config.rewrite_enabled = False
        mock_research_config.search_results = 10
        mock_research_config.chunk_size = 1000
        mock_research_config.chunk_overlap = 200
        mock_research_config.top_chunks = 10

        mock_generate_sub_queries.return_value = [
            "React components tutorial",
            "Vue.js getting started guide",
        ]

        with patch(
            "web_mcp.research.pipeline.get_research_config", return_value=mock_research_config
        ):
            from web_mcp.research.pipeline import research

            await research("Compare React and Vue")

        assert mock_search.call_count == 1
