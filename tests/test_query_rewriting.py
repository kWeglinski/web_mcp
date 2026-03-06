"""Unit tests for query rewriting utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_mcp.llm.client import LLMError
from web_mcp.research.query_rewriting import (
    expand_query_with_keywords,
    generate_query_variants,
    generate_sub_queries,
    parallel_search_queries,
    rewrite_query,
)


class TestExpandQueryWithKeywords:
    """Tests for expand_query_with_keywords function (pure function)."""

    def test_expand_simple_query(self):
        """Test expansion of a simple query."""
        query = "python"
        result = expand_query_with_keywords(query)

        assert "python site:wikipedia.org" in result
        assert "define python" in result
        assert "python tutorial" in result
        assert "best python guide" in result
        assert " OR " in result

    def test_expand_multi_word_query(self):
        """Test expansion of a multi-word query."""
        query = "machine learning algorithms"
        result = expand_query_with_keywords(query)

        assert "machine learning algorithms site:wikipedia.org" in result
        assert "define machine learning algorithms" in result
        assert "machine learning algorithms tutorial" in result
        assert "best machine learning algorithms guide" in result

    def test_expand_query_with_special_characters(self):
        """Test expansion of query with special characters."""
        query = "C++ programming"
        result = expand_query_with_keywords(query)

        assert "C++ programming site:wikipedia.org" in result
        assert "define C++ programming" in result
        assert "C++ programming tutorial" in result

    def test_expand_query_with_numbers(self):
        """Test expansion of query with numbers."""
        query = "Python 3.12"
        result = expand_query_with_keywords(query)

        assert "Python 3.12 site:wikipedia.org" in result
        assert "define Python 3.12" in result

    def test_expand_empty_query(self):
        """Test expansion of empty query."""
        query = ""
        result = expand_query_with_keywords(query)

        assert " site:wikipedia.org" in result
        assert "define " in result
        assert " tutorial" in result
        assert "best  guide" in result

    def test_expand_query_with_whitespace(self):
        """Test expansion of query with leading/trailing whitespace."""
        query = "  docker  "
        result = expand_query_with_keywords(query)

        assert "  docker   site:wikipedia.org" in result

    def test_expand_long_query(self):
        """Test expansion of a long query."""
        query = "how to implement a binary search tree in Python with balanced operations"
        result = expand_query_with_keywords(query)

        assert query in result
        assert " OR " in result

    def test_expand_returns_string(self):
        """Test that result is a string."""
        query = "test"
        result = expand_query_with_keywords(query)

        assert isinstance(result, str)

    def test_expand_contains_four_patterns(self):
        """Test that result contains exactly four patterns joined by OR."""
        query = "test"
        result = expand_query_with_keywords(query)

        parts = result.split(" OR ")
        assert len(parts) == 4


class TestRewriteQuery:
    """Tests for rewrite_query function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_configured(self):
        """Create a mock configured LLM config."""
        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock:
            config = MagicMock()
            config.is_configured = True
            mock.return_value = config
            yield mock

    @pytest.fixture
    def mock_not_configured(self):
        """Create a mock unconfigured LLM config."""
        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock:
            config = MagicMock()
            config.is_configured = False
            mock.return_value = config
            yield mock

    @pytest.mark.asyncio
    async def test_rewrite_success(self, mock_client, mock_configured):
        """Test successful query rewrite."""
        mock_client.chat = AsyncMock(return_value="optimized search query")

        result = await rewrite_query(mock_client, "how do I learn python?")

        assert result == "optimized search query"
        mock_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_rewrite_not_configured(self, mock_client, mock_not_configured):
        """Test rewrite when LLM is not configured."""
        result = await rewrite_query(mock_client, "test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_rewrite_llm_error(self, mock_client, mock_configured):
        """Test rewrite when LLM raises an error."""
        mock_client.chat = AsyncMock(side_effect=LLMError("API error"))

        result = await rewrite_query(mock_client, "test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_rewrite_generic_exception(self, mock_client, mock_configured):
        """Test rewrite when generic exception occurs."""
        mock_client.chat = AsyncMock(side_effect=Exception("Unexpected error"))

        result = await rewrite_query(mock_client, "test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_rewrite_empty_response(self, mock_client, mock_configured):
        """Test rewrite when LLM returns empty string."""
        mock_client.chat = AsyncMock(return_value="   ")

        result = await rewrite_query(mock_client, "test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_rewrite_strips_whitespace(self, mock_client, mock_configured):
        """Test that rewrite strips whitespace from result."""
        mock_client.chat = AsyncMock(return_value="  optimized query  ")

        result = await rewrite_query(mock_client, "test query")

        assert result == "optimized query"

    @pytest.mark.asyncio
    async def test_rewrite_uses_correct_parameters(self, mock_client, mock_configured):
        """Test that rewrite uses correct LLM parameters."""
        mock_client.chat = AsyncMock(return_value="result")

        await rewrite_query(mock_client, "test query")

        call_args = mock_client.chat.call_args
        assert call_args[1]["max_tokens"] == 100
        assert call_args[1]["temperature"] == 0.3
        messages = call_args[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "test query"


class TestGenerateSubQueries:
    """Tests for generate_sub_queries function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_configured(self):
        """Create a mock configured LLM config."""
        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock:
            config = MagicMock()
            config.is_configured = True
            mock.return_value = config
            yield mock

    @pytest.fixture
    def mock_not_configured(self):
        """Create a mock unconfigured LLM config."""
        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock:
            config = MagicMock()
            config.is_configured = False
            mock.return_value = config
            yield mock

    @pytest.mark.asyncio
    async def test_generate_sub_queries_success(self, mock_client, mock_configured):
        """Test successful sub-query generation."""
        mock_client.chat = AsyncMock(
            return_value="1. Python basics tutorial\n2. Python advanced concepts\n3. Python best practices"
        )

        result = await generate_sub_queries(mock_client, "learn python")

        assert len(result) == 3
        assert "Python basics tutorial" in result
        assert "Python advanced concepts" in result
        assert "Python best practices" in result

    @pytest.mark.asyncio
    async def test_generate_sub_queries_not_configured(self, mock_client, mock_not_configured):
        """Test sub-query generation when LLM is not configured."""
        result = await generate_sub_queries(mock_client, "test query")

        assert result == ["test query"]

    @pytest.mark.asyncio
    async def test_generate_sub_queries_exception(self, mock_client, mock_configured):
        """Test sub-query generation when exception occurs."""
        mock_client.chat = AsyncMock(side_effect=Exception("Error"))

        result = await generate_sub_queries(mock_client, "test query")

        assert result == ["test query"]

    @pytest.mark.asyncio
    async def test_generate_sub_queries_empty_response(self, mock_client, mock_configured):
        """Test sub-query generation with empty LLM response."""
        mock_client.chat = AsyncMock(return_value="")

        result = await generate_sub_queries(mock_client, "test query")

        assert result == ["test query"]

    @pytest.mark.asyncio
    async def test_generate_sub_queries_with_bullet_points(self, mock_client, mock_configured):
        """Test parsing sub-queries with bullet points."""
        mock_client.chat = AsyncMock(return_value="- First query\n- Second query\n* Third query")

        result = await generate_sub_queries(mock_client, "test query")

        assert len(result) == 3
        assert "First query" in result
        assert "Second query" in result
        assert "Third query" in result

    @pytest.mark.asyncio
    async def test_generate_sub_queries_with_special_bullet(self, mock_client, mock_configured):
        """Test parsing sub-queries with special bullet character."""
        mock_client.chat = AsyncMock(return_value="• First query\n• Second query")

        result = await generate_sub_queries(mock_client, "test query")

        assert len(result) == 2
        assert "First query" in result
        assert "Second query" in result

    @pytest.mark.asyncio
    async def test_generate_sub_queries_strips_numbered_prefixes(
        self, mock_client, mock_configured
    ):
        """Test that numbered prefixes are stripped."""
        mock_client.chat = AsyncMock(
            return_value="1. First\n2. Second\n3. Third\n4. Fourth\n5. Fifth"
        )

        result = await generate_sub_queries(mock_client, "test query")

        assert "First" in result
        assert "Second" in result
        assert "Third" in result
        assert "Fourth" in result
        assert "Fifth" in result

    @pytest.mark.asyncio
    async def test_generate_sub_queries_skips_empty_lines(self, mock_client, mock_configured):
        """Test that empty lines are skipped."""
        mock_client.chat = AsyncMock(return_value="1. First\n\n2. Second\n\n")

        result = await generate_sub_queries(mock_client, "test query")

        assert len(result) == 2
        assert "First" in result
        assert "Second" in result

    @pytest.mark.asyncio
    async def test_generate_sub_queries_uses_correct_parameters(self, mock_client, mock_configured):
        """Test that generate_sub_queries uses correct LLM parameters."""
        mock_client.chat = AsyncMock(return_value="1. Query one")

        await generate_sub_queries(mock_client, "test query")

        call_args = mock_client.chat.call_args
        assert call_args[1]["max_tokens"] == 200
        assert call_args[1]["temperature"] == 0.3


class TestGenerateQueryVariants:
    """Tests for generate_query_variants function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_configured(self):
        """Create a mock configured LLM config."""
        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock:
            config = MagicMock()
            config.is_configured = True
            mock.return_value = config
            yield mock

    @pytest.fixture
    def mock_not_configured(self):
        """Create a mock unconfigured LLM config."""
        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock:
            config = MagicMock()
            config.is_configured = False
            mock.return_value = config
            yield mock

    @pytest.mark.asyncio
    async def test_generate_variants_success(self, mock_client, mock_configured):
        """Test successful variant generation."""
        mock_client.chat = AsyncMock(return_value="1. variant one\n2. variant two")

        result = await generate_query_variants(mock_client, "test query")

        assert len(result) >= 1
        assert "test query" in result

    @pytest.mark.asyncio
    async def test_generate_variants_not_configured(self, mock_client, mock_not_configured):
        """Test variant generation when LLM is not configured."""
        result = await generate_query_variants(mock_client, "test query")

        assert result == ["test query"]

    @pytest.mark.asyncio
    async def test_generate_variants_exception(self, mock_client, mock_configured):
        """Test variant generation when exception occurs in sub-queries."""
        mock_client.chat = AsyncMock(side_effect=Exception("Error"))

        result = await generate_query_variants(mock_client, "test query")

        assert "test query" in result
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_generate_variants_includes_expanded(self, mock_client, mock_configured):
        """Test that variants include keyword-expanded version."""
        mock_client.chat = AsyncMock(return_value="1. sub query")

        result = await generate_query_variants(mock_client, "python")

        expanded = expand_query_with_keywords("python")
        assert expanded in result

    @pytest.mark.asyncio
    async def test_generate_variants_no_duplicates(self, mock_client, mock_configured):
        """Test that variants don't include duplicates."""
        mock_client.chat = AsyncMock(return_value="1. test query\n2. test query")

        result = await generate_query_variants(mock_client, "test query")

        original_count = sum(1 for v in result if v == "test query")
        assert original_count == 1

    @pytest.mark.asyncio
    async def test_generate_variants_includes_original(self, mock_client, mock_configured):
        """Test that original query is always included."""
        mock_client.chat = AsyncMock(return_value="1. other query")

        result = await generate_query_variants(mock_client, "original query")

        assert "original query" in result


class TestParallelSearchQueries:
    """Tests for parallel_search_queries function."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def mock_configured(self):
        """Create a mock configured LLM config."""
        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock:
            config = MagicMock()
            config.is_configured = True
            mock.return_value = config
            yield mock

    @pytest.fixture
    def mock_not_configured(self):
        """Create a mock unconfigured LLM config."""
        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock:
            config = MagicMock()
            config.is_configured = False
            mock.return_value = config
            yield mock

    @pytest.mark.asyncio
    async def test_parallel_search_success(self, mock_client, mock_configured):
        """Test successful parallel search."""
        mock_client.chat = AsyncMock(return_value="1. sub query")
        mock_search = AsyncMock(return_value=[{"result": "data"}])

        result = await parallel_search_queries(mock_client, "test query", mock_search)

        assert len(result) >= 1
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_parallel_search_not_configured(self, mock_client, mock_not_configured):
        """Test parallel search when LLM is not configured."""
        mock_search = AsyncMock(return_value=[{"result": "data"}])

        result = await parallel_search_queries(mock_client, "test query", mock_search)

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_parallel_search_combines_list_results(self, mock_client, mock_configured):
        """Test that list results are combined."""
        mock_client.chat = AsyncMock(return_value="1. sub query")
        mock_search = AsyncMock(return_value=[{"id": 1}, {"id": 2}])

        result = await parallel_search_queries(
            mock_client, "test query", mock_search, max_concurrent=2
        )

        assert all(isinstance(r, dict) for r in result)

    @pytest.mark.asyncio
    async def test_parallel_search_combines_dict_results(self, mock_client, mock_configured):
        """Test that dict results are appended."""
        mock_client.chat = AsyncMock(return_value="1. sub query")
        mock_search = AsyncMock(return_value={"single": "result"})

        result = await parallel_search_queries(
            mock_client, "test query", mock_search, max_concurrent=1
        )

        assert {"single": "result"} in result

    @pytest.mark.asyncio
    async def test_parallel_search_handles_exceptions(self, mock_client, mock_configured):
        """Test that exceptions in search are handled gracefully."""
        mock_client.chat = AsyncMock(return_value="1. sub query")
        mock_search = AsyncMock(side_effect=Exception("Search failed"))

        result = await parallel_search_queries(mock_client, "test query", mock_search)

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_parallel_search_respects_max_concurrent(self, mock_client, mock_configured):
        """Test that max_concurrent limits the number of variants searched."""
        mock_client.chat = AsyncMock(return_value="1. sub one\n2. sub two\n3. sub three")
        mock_search = AsyncMock(return_value=[{"result": "data"}])

        await parallel_search_queries(mock_client, "test query", mock_search, max_concurrent=2)

        assert mock_search.call_count >= 2

    @pytest.mark.asyncio
    async def test_parallel_search_with_empty_variants(self, mock_client, mock_configured):
        """Test parallel search with empty variants."""
        mock_client.chat = AsyncMock(return_value="")
        mock_search = AsyncMock(return_value=[{"result": "data"}])

        result = await parallel_search_queries(mock_client, "test query", mock_search)

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_parallel_search_mixed_results(self, mock_client, mock_configured):
        """Test parallel search with mixed result types."""
        mock_client.chat = AsyncMock(return_value="1. sub query")
        call_count = 0

        async def mixed_search(query):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return [{"id": 1}]
            else:
                return {"single": "result"}

        result = await parallel_search_queries(
            mock_client, "test query", mixed_search, max_concurrent=1
        )

        assert isinstance(result, list)


class TestEdgeCases:
    """Tests for edge cases across all functions."""

    def test_expand_query_unicode(self):
        """Test expand_query_with_keywords with unicode characters."""
        query = "日本語 テスト"
        result = expand_query_with_keywords(query)

        assert "日本語 テスト" in result

    def test_expand_query_newlines(self):
        """Test expand_query_with_keywords with newlines."""
        query = "query\nwith\nnewlines"
        result = expand_query_with_keywords(query)

        assert "query\nwith\nnewlines" in result

    def test_expand_query_tabs(self):
        """Test expand_query_with_keywords with tabs."""
        query = "query\twith\ttabs"
        result = expand_query_with_keywords(query)

        assert "query\twith\ttabs" in result

    @pytest.mark.asyncio
    async def test_rewrite_query_unicode(self):
        """Test rewrite_query with unicode characters."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value="日本語クエリ")

        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock_config:
            config = MagicMock()
            config.is_configured = True
            mock_config.return_value = config

            result = await rewrite_query(mock_client, "日本語")

            assert result == "日本語クエリ"

    @pytest.mark.asyncio
    async def test_generate_sub_queries_unicode(self):
        """Test generate_sub_queries with unicode characters."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value="1. 日本語一つ\n2. 日本語二つ")

        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock_config:
            config = MagicMock()
            config.is_configured = True
            mock_config.return_value = config

            result = await generate_sub_queries(mock_client, "日本語")

            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_parallel_search_empty_query(self):
        """Test parallel_search_queries with empty query."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value="1. sub")
        mock_search = AsyncMock(return_value=[])

        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock_config:
            config = MagicMock()
            config.is_configured = True
            mock_config.return_value = config

            result = await parallel_search_queries(mock_client, "", mock_search)

            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_parallel_search_none_results(self):
        """Test parallel_search_queries when search returns None."""
        mock_client = MagicMock()
        mock_client.chat = AsyncMock(return_value="1. sub")
        mock_search = AsyncMock(return_value=None)

        with patch("web_mcp.research.query_rewriting.get_llm_config") as mock_config:
            config = MagicMock()
            config.is_configured = True
            mock_config.return_value = config

            result = await parallel_search_queries(mock_client, "test", mock_search)

            assert isinstance(result, list)
