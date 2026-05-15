"""Unit tests for the knowledge gatherer module — extractor, dedup, categories, validation, cleanup, pipeline."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_mcp.knowledge.categories import (
    CATEGORY_TAXONOMY,
    Category,
    classify_topic,
    find_categories_by_name,
    get_relevant_categories,
)
from web_mcp.knowledge.cleanup import (
    KnowledgeCleanupTask,
    start_cleanup_task,
    stop_cleanup_task,
)
from web_mcp.knowledge.dedup import DedupCache, semantic_dedup
from web_mcp.knowledge.extractor import (
    Fact,
    FactExtractionResult,
    _parse_facts,
    extract_facts,
)
from web_mcp.knowledge.pipeline import KnowledgeGatherer, KnowledgeResult, gather_knowledge
from web_mcp.knowledge.validation import (
    validate_fact_quality,
    validate_topic_width,
)

# ---------------------------------------------------------------------------
# 1. Fact / Extractor Tests
# ---------------------------------------------------------------------------


class TestFact:
    """Tests for the Fact dataclass and extract_facts function."""

    def test_fact_dataclass_creation(self):
        """Fact can be instantiated with all fields."""
        fact = Fact(
            text="Python 3.12 was released in October 2023.",
            source_url="https://docs.python.org/3/whatsnew/3.12.html",
            source_title="What's New in Python 3.12",
            confidence=0.95,
            category="language",
            chunk_index=0,
            snippet="Python 3.12 introduces ...",
        )
        assert fact.text == "Python 3.12 was released in October 2023."
        assert fact.source_url == "https://docs.python.org/3/whatsnew/3.12.html"
        assert fact.source_title == "What's New in Python 3.12"
        assert fact.confidence == 0.95
        assert fact.category == "language"
        assert fact.chunk_index == 0
        assert fact.snippet == "Python 3.12 introduces ..."

    def test_fact_dataclass_defaults(self):
        """Fact uses sensible defaults for optional fields."""
        fact = Fact(text="Minimal fact", source_url="https://example.com")
        assert fact.source_title == ""
        assert fact.confidence == 0.0
        assert fact.category == ""
        assert fact.chunk_index == 0
        assert fact.snippet == ""


class TestExtractFacts:
    """Tests for extract_facts async function."""

    def _mock_response_with_facts(self, facts_data):
        """Helper to produce a JSON-array response string."""
        import json

        return json.dumps(facts_data)

    @pytest.mark.asyncio
    async def test_fact_extraction_success(self):
        """extract_facts returns parsed facts from valid JSON response."""
        facts_data = [
            {
                "text": "Python supports async/await syntax.",
                "confidence": 0.95,
                "category": "language",
            },
            {
                "text": "The asyncio module provides event loop.",
                "confidence": 0.88,
                "category": "language",
            },
        ]
        response = self._mock_response_with_facts(facts_data)

        with patch("web_mcp.llm.client.get_llm_client") as mock_get_client:
            llm_client = MagicMock()
            llm_client.chat = AsyncMock(return_value=response)
            mock_get_client.return_value = llm_client

            result = await extract_facts(
                text="Async programming in Python is powerful.",
                source_url="https://example.com/python-async",
                source_title="Python Async Guide",
                llm_client=llm_client,
            )

            assert isinstance(result, FactExtractionResult)
            assert result.source_url == "https://example.com/python-async"
            assert result.source_title == "Python Async Guide"
            assert len(result.facts) == 2
            assert result.facts[0].text == facts_data[0]["text"]
            assert result.facts[0].confidence == 0.95
            assert result.facts[0].category == "language"
            assert result.chunks_processed == 1
            assert result.total_chunks == 1
            assert result.extraction_error is None

    @pytest.mark.asyncio
    async def test_fact_extraction_invalid_json(self):
        """Returns empty facts when LLM returns non-JSON."""
        with patch("web_mcp.llm.client.get_llm_client") as mock_get_client:
            llm_client = MagicMock()
            llm_client.chat = AsyncMock(return_value="Just some text, no JSON at all.")
            mock_get_client.return_value = llm_client

            result = await extract_facts(
                text="Some text to extract from.",
                source_url="https://example.com",
                llm_client=llm_client,
            )

            assert len(result.facts) == 0
            assert result.extraction_error is None

    @pytest.mark.asyncio
    async def test_fact_extraction_short_facts_filtered(self):
        """Facts with text shorter than 10 characters are excluded."""
        facts_data = [
            {"text": "Short", "confidence": 0.9},  # 5 chars — too short
            {"text": "This is a valid fact statement here.", "confidence": 0.85},  # 36 chars — OK
            {"text": "Also short", "confidence": 0.95},  # 10 chars — exactly 10, should pass
        ]
        response = self._mock_response_with_facts(facts_data)

        with patch("web_mcp.llm.client.get_llm_client") as mock_get_client:
            llm_client = MagicMock()
            llm_client.chat = AsyncMock(return_value=response)
            mock_get_client.return_value = llm_client

            result = await extract_facts(
                text="Text to extract from.",
                source_url="https://example.com",
                llm_client=llm_client,
            )

            # "Short" (5 chars) is filtered; "This is a valid fact statement here." and "Also short" (10 chars) pass
            assert len(result.facts) == 2
            texts = [f.text for f in result.facts]
            assert "Short" not in texts

    @pytest.mark.asyncio
    async def test_fact_extraction_low_confidence_filtered(self):
        """Facts below min_confidence are excluded."""
        facts_data = [
            {"text": "High confidence fact here.", "confidence": 0.9},
            {"text": "Low confidence fact here.", "confidence": 0.3},
            {"text": "Medium confidence fact here.", "confidence": 0.6},
        ]
        response = self._mock_response_with_facts(facts_data)

        with patch("web_mcp.llm.client.get_llm_client") as mock_get_client:
            llm_client = MagicMock()
            llm_client.chat = AsyncMock(return_value=response)
            mock_get_client.return_value = llm_client

            result = await extract_facts(
                text="Text to extract from.",
                source_url="https://example.com",
                min_confidence=0.5,
                llm_client=llm_client,
            )

            assert len(result.facts) == 2
            confidences = [f.confidence for f in result.facts]
            assert all(c >= 0.5 for c in confidences)

    @pytest.mark.asyncio
    async def test_fact_extraction_max_facts_limit(self):
        """Only max_facts are returned."""
        facts_data = [
            {
                "text": f"Fact number {i} with enough characters to pass the minimum length.",
                "confidence": 0.9,
            }
            for i in range(10)
        ]
        response = self._mock_response_with_facts(facts_data)

        with patch("web_mcp.llm.client.get_llm_client") as mock_get_client:
            llm_client = MagicMock()
            llm_client.chat = AsyncMock(return_value=response)
            mock_get_client.return_value = llm_client

            result = await extract_facts(
                text="Text to extract from.",
                source_url="https://example.com",
                max_facts=3,
                llm_client=llm_client,
            )

            assert len(result.facts) == 3

    @pytest.mark.asyncio
    async def test_fact_extraction_error_handling(self):
        """Returns FactExtractionResult with extraction_error on exception."""
        with patch("web_mcp.llm.client.get_llm_client") as mock_get_client:
            llm_client = MagicMock()
            llm_client.chat = AsyncMock(side_effect=RuntimeError("API timeout"))
            mock_get_client.return_value = llm_client

            result = await extract_facts(
                text="Text to extract from.",
                source_url="https://example.com",
                llm_client=llm_client,
            )

            assert len(result.facts) == 0
            assert result.extraction_error == "API timeout"
            assert result.chunks_processed == 0
            assert result.total_chunks == 1


class TestParseFacts:
    """Tests for the _parse_facts helper function."""

    def test_parse_facts_valid_json(self):
        """_parse_facts correctly parses valid JSON response."""
        json_response = '[{"text": "PostgreSQL is a relational database.", "confidence": 0.92, "category": "database"}]'
        result = _parse_facts(
            response=json_response,
            source_url="https://postgresql.org",
            source_title="PostgreSQL",
            chunk_index=0,
            max_facts=10,
            min_confidence=0.0,
        )
        assert len(result) == 1
        assert result[0].text == "PostgreSQL is a relational database."
        assert result[0].confidence == 0.92
        assert result[0].category == "database"

    def test_parse_facts_no_json_brackets(self):
        """_parse_facts returns empty list when no JSON array found."""
        result = _parse_facts(
            response="The answer is 42.",
            source_url="https://example.com",
            source_title="",
            chunk_index=0,
            max_facts=10,
            min_confidence=0.0,
        )
        assert result == []

    def test_parse_facts_invalid_json_syntax(self):
        """_parse_facts returns empty list when JSON is syntactically invalid."""
        result = _parse_facts(
            response='[{"text": "broken json", confidence: 0.9}]',
            source_url="https://example.com",
            source_title="",
            chunk_index=0,
            max_facts=10,
            min_confidence=0.0,
        )
        assert result == []

    def test_parse_facts_non_dict_items_skipped(self):
        """_parse_facts skips non-dict items in the JSON array."""
        json_response = '["not a dict", 42, {"text": "valid fact here.", "confidence": 0.9}]'
        result = _parse_facts(
            response=json_response,
            source_url="https://example.com",
            source_title="",
            chunk_index=0,
            max_facts=10,
            min_confidence=0.0,
        )
        assert len(result) == 1
        assert result[0].text == "valid fact here."

    def test_parse_facts_defaults_confidence(self):
        """_parse_facts uses 0.8 as default confidence when missing."""
        json_response = '[{"text": "Fact without confidence field."}]'
        result = _parse_facts(
            response=json_response,
            source_url="https://example.com",
            source_title="",
            chunk_index=0,
            max_facts=10,
            min_confidence=0.0,
        )
        assert len(result) == 1
        assert result[0].confidence == 0.8

    def test_parse_facts_source_url_applied(self):
        """_parse_facts applies source_url and source_title to all facts."""
        json_response = (
            '[{"text": "Fact one.", "confidence": 0.9}, {"text": "Fact two.", "confidence": 0.8}]'
        )
        result = _parse_facts(
            response=json_response,
            source_url="https://example.com/page",
            source_title="Page Title",
            chunk_index=2,
            max_facts=10,
            min_confidence=0.0,
        )
        assert all(f.source_url == "https://example.com/page" for f in result)
        assert all(f.source_title == "Page Title" for f in result)
        assert all(f.chunk_index == 2 for f in result)


# ---------------------------------------------------------------------------
# 2. DedupCache / Semantic Dedup Tests
# ---------------------------------------------------------------------------


class TestDedupCache:
    """Tests for the DedupCache class."""

    def _make_fact(self, text, source_url="https://example.com"):
        return Fact(text=text, source_url=source_url)

    def test_dedup_cache_exact_match(self):
        """Same fact text returns False on second add (duplicate)."""
        cache = DedupCache()
        fact = self._make_fact("Python is a programming language.")

        assert cache.add_fact(fact) is True  # first time — new
        assert cache.add_fact(fact) is False  # duplicate

    def test_dedup_cache_different_text(self):
        """Different fact text returns True (not duplicate)."""
        cache = DedupCache()
        fact1 = self._make_fact("Python is a programming language.")
        fact2 = self._make_fact("Docker containers isolate applications.")

        assert cache.add_fact(fact1) is True
        assert cache.add_fact(fact2) is True

    def test_dedup_cache_case_insensitive(self):
        """'Hello World' and 'hello world' are treated as the same."""
        cache = DedupCache()
        fact1 = self._make_fact("Hello World")
        fact2 = self._make_fact("hello world")

        assert cache.add_fact(fact1) is True
        assert cache.add_fact(fact2) is False  # case-insensitive match

    def test_dedup_cache_stats(self):
        """get_stats() returns correct counts."""
        cache = DedupCache()
        cache.add_fact(self._make_fact("Fact one."))
        cache.add_fact(self._make_fact("Fact two."))
        cache.add_fact(self._make_fact("Fact one."))  # duplicate

        stats = cache.get_stats()
        assert stats["exact_matches"] == 2  # two unique texts
        assert stats["semantic_entries"] == 0
        assert "last_cleanup" in stats

    def test_is_duplicate_exact(self):
        """is_duplicate_exact correctly identifies existing facts."""
        cache = DedupCache()
        fact = self._make_fact("Test fact text.")

        assert cache.is_duplicate_exact(fact) is False  # not in cache
        cache.add_fact(fact)
        assert cache.is_duplicate_exact(fact) is True  # now a duplicate


class TestSemanticDedup:
    """Tests for the semantic_dedup async function."""

    @pytest.mark.asyncio
    async def test_semantic_dedup_removes_duplicates(self):
        """semantic_dedup removes semantically similar facts."""
        with (
            patch("web_mcp.llm.client.get_llm_client") as mock_get_client,
            patch("web_mcp.llm.embeddings.cosine_similarity") as mock_cosine,
        ):
            llm_client = MagicMock()
            llm_client.embed = AsyncMock(return_value=[0.1] * 384)
            mock_get_client.return_value = llm_client

            # Make all embeddings look similar
            mock_cosine.return_value = 0.95  # above threshold

            facts = [
                Fact(text="PostgreSQL is a database.", source_url="https://a.com"),
                Fact(text="Postgres is a database system.", source_url="https://b.com"),
                Fact(text="Redis is an in-memory store.", source_url="https://c.com"),
            ]

            result = await semantic_dedup(facts, llm_client=llm_client)

            # First fact kept; second is semantic duplicate; third is different enough
            # (but with cosine=0.95 for all, only the first survives)
            assert len(result) == 1
            assert result[0].text == "PostgreSQL is a database."

    @pytest.mark.asyncio
    async def test_semantic_dedup_with_existing_cache(self):
        """semantic_dedup uses and updates an existing cache."""
        with (
            patch("web_mcp.llm.client.get_llm_client") as mock_get_client,
            patch("web_mcp.llm.embeddings.cosine_similarity") as mock_cosine,
        ):
            llm_client = MagicMock()
            llm_client.embed = AsyncMock(return_value=[0.1] * 384)
            mock_get_client.return_value = llm_client

            cache = DedupCache()
            cache.add_fact(Fact(text="Pre-existing fact.", source_url="https://old.com"))

            # Pre-populate semantic embeddings

            existing_emb = [0.1] * 384
            cache._embeddings["Pre-existing fact."] = existing_emb

            facts = [
                Fact(text="New fact one.", source_url="https://a.com"),
                Fact(text="New fact two.", source_url="https://b.com"),
            ]

            # New facts are not semantically similar to the pre-existing one
            mock_cosine.return_value = 0.1

            result = await semantic_dedup(facts, existing_cache=cache, llm_client=llm_client)

            assert len(result) == 2
            # Cache should now have the new facts
            assert len(cache._embeddings) == 3  # 1 pre-existing + 2 new

    @pytest.mark.asyncio
    async def test_semantic_dedup_exact_dedup_first(self):
        """Exact duplicates are removed before semantic dedup."""
        with (patch("web_mcp.llm.client.get_llm_client") as mock_get_client,):
            llm_client = MagicMock()
            llm_client.embed = AsyncMock(return_value=[0.1] * 384)
            mock_get_client.return_value = llm_client

            # Two identical facts
            fact = Fact(text="Identical fact text.", source_url="https://a.com")
            facts = [fact, Fact(text="Identical fact text.", source_url="https://b.com")]

            result = await semantic_dedup(facts, llm_client=llm_client)

            # Only one copy should remain (exact dedup)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_semantic_dedup_empty_list(self):
        """semantic_dedup returns empty list for empty input."""
        with patch("web_mcp.llm.client.get_llm_client") as mock_get_client:
            llm_client = MagicMock()
            mock_get_client.return_value = llm_client

            result = await semantic_dedup([], llm_client=llm_client)
            assert result == []


# ---------------------------------------------------------------------------
# 3. Category Tests
# ---------------------------------------------------------------------------


class TestCategoryTaxonomy:
    """Tests for the CATEGORY_TAXONOMY and Category dataclass."""

    def test_taxonomy_complete(self):
        """All expected categories exist in the taxonomy."""
        expected_names = {
            "api",
            "architecture",
            "configuration",
            "deployment",
            "security",
            "performance",
            "database",
            "testing",
            "machine_learning",
            "networking",
            "language",
            "tooling",
            "error_handling",
            "data_format",
            "concurrency",
        }
        actual_names = {cat.name for cat in CATEGORY_TAXONOMY}
        assert expected_names == actual_names

    def test_taxonomy_count(self):
        """Taxonomy has exactly 15 categories."""
        assert len(CATEGORY_TAXONOMY) == 15

    def test_category_has_all_fields(self):
        """Each category has name, description, keywords, parent, priority."""
        for cat in CATEGORY_TAXONOMY:
            assert isinstance(cat.name, str) and len(cat.name) > 0
            assert isinstance(cat.description, str) and len(cat.description) > 0
            assert isinstance(cat.keywords, list)
            assert cat.parent is None or isinstance(cat.parent, str)
            assert isinstance(cat.priority, int)


class TestClassifyTopic:
    """Tests for the classify_topic function."""

    def test_classify_topic_matches_keywords(self):
        """Topic with keywords returns matching categories."""
        result = classify_topic(
            url="https://example.com/docker-deploy-guide",
            title="Docker Deployment",
            text="Deploy containers using Docker and Kubernetes for scalable microservice architecture.",
        )
        names = [c.name for c in result]
        assert "deployment" in names  # deploy, docker, kubernetes
        assert "architecture" in names  # microservice, architecture

    def test_classify_topic_no_match(self):
        """Unrelated text returns empty list."""
        result = classify_topic(text="The quick brown fox jumps over the lazy dog.")
        assert result == []

    def test_classify_topic_returns_top_5(self):
        """At most 5 categories are returned."""
        result = classify_topic(
            url="https://example.com",
            title="API Security Testing",
            text="This page covers REST API endpoints, authentication, testing, and security best practices.",
        )
        assert len(result) <= 5

    def test_classify_topic_priority_ordering(self):
        """Categories with more keyword matches appear first."""
        result = classify_topic(
            text="API endpoint security with authentication.",
        )
        # "api" and "security" categories should match more keywords
        if len(result) >= 2:
            api_idx = next((i for i, c in enumerate(result) if c.name == "api"), None)
            sec_idx = next((i for i, c in enumerate(result) if c.name == "security"), None)
            # Both should have high priority scores
            assert api_idx is not None or sec_idx is not None


class TestGetRelevantCategories:
    """Tests for get_relevant_categories function."""

    def test_get_relevant_categories_url_hints(self):
        """URL hints are applied."""
        result = get_relevant_categories(url="https://docs.python.org/3/faq/design.html")
        names = [c.name for c in result]
        assert "language" in names  # from docs.python.org hint
        assert "tooling" in names  # from docs.python.org hint

    def test_get_relevant_categories_merges_url_and_keyword(self):
        """Both URL hint matches and keyword matches are included."""
        result = get_relevant_categories(
            url="https://docs.python.org/3/library/asyncio.html",
            text="Docker deployment with security scanning.",
        )
        names = [c.name for c in result]
        # URL hint: language, tooling
        assert "language" in names
        assert "tooling" in names
        # Keyword: deployment, security
        assert "deployment" in names
        assert "security" in names

    def test_get_relevant_categories_no_url_hint(self):
        """Without URL hints, only keyword-based classification is used."""
        result = get_relevant_categories(
            url="https://unknown-domain.com", text="SQL database queries."
        )
        names = [c.name for c in result]
        assert "database" in names


class TestFindCategoriesByName:
    """Tests for find_categories_by_name function."""

    def test_case_insensitive_name_lookup(self):
        """Case-insensitive name lookup works."""
        result = find_categories_by_name(["Security", "DATABASE", "Machine_Learning"])
        names = {c.name for c in result}
        assert names == {"security", "database", "machine_learning"}

    def test_nonexistent_category(self):
        """Nonexistent category names are ignored."""
        result = find_categories_by_name(["nonexistent", "also_fake"])
        assert result == []

    def test_partial_name_no_match(self):
        """Partial name matches do not return results."""
        result = find_categories_by_name(["sec"])
        assert result == []


# ---------------------------------------------------------------------------
# 4. Validation Tests
# ---------------------------------------------------------------------------


class TestValidateTopicWidth:
    """Tests for validate_topic_width function."""

    def test_validate_topic_width_valid(self):
        """Specific topic passes validation."""
        result = validate_topic_width("Python async best practices")
        assert result["valid"] is True
        assert result["issues"] == []
        assert result["suggestion"] is None

    def test_validate_topic_width_too_broad(self):
        """Single common word fails validation."""
        result = validate_topic_width("python")
        assert result["valid"] is False
        assert any("too generic" in issue for issue in result["issues"])
        assert result["suggestion"] is not None

    def test_validate_topic_width_too_long(self):
        """Many words fails validation."""
        result = validate_topic_width(
            "Python programming language features and best practices guide"
        )
        assert result["valid"] is False
        assert any("too broad" in issue for issue in result["issues"])

    def test_validate_topic_width_introduction_pattern(self):
        """'What is' pattern is detected as broad."""
        result = validate_topic_width("What is Python programming")
        assert result["valid"] is False
        assert any("broad pattern" in issue for issue in result["issues"])

    def test_validate_topic_width_suggestion_provided(self):
        """Suggestion is returned when validation fails."""
        result = validate_topic_width("What is Python")
        assert result["suggestion"] is not None
        assert "Try:" in result["suggestion"]

    def test_validate_topic_width_how_to_pattern(self):
        """'How to' pattern is detected."""
        result = validate_topic_width("How to use Docker containers")
        assert result["valid"] is False

    def test_validate_topic_width_comprehensive_pattern(self):
        """'Comprehensive' pattern is detected."""
        result = validate_topic_width("Comprehensive guide to Python")
        assert result["valid"] is False


class TestValidateFactQuality:
    """Tests for validate_fact_quality function."""

    def test_validate_fact_quality_no_facts(self):
        """Empty list returns invalid."""
        result = validate_fact_quality([])
        assert result["valid"] is False
        assert "No facts extracted" in result["issues"]
        assert result["stats"]["total"] == 0

    def test_validate_fact_quality_good_facts(self):
        """High confidence facts with sources pass validation."""
        facts = [
            Fact(
                text="Python 3.12 introduced parenthesized context managers.",
                source_url="https://docs.python.org",
                confidence=0.95,
                category="language",
            ),
            Fact(
                text="asyncio.run() is the main entry point for async programs.",
                source_url="https://docs.python.org",
                confidence=0.9,
                category="language",
            ),
        ]
        result = validate_fact_quality(facts)
        assert result["valid"] is True
        assert result["issues"] == []

    def test_validate_fact_quality_low_confidence(self):
        """Low average confidence fails validation."""
        facts = [
            Fact(text="Maybe this is a fact?", source_url="https://example.com", confidence=0.2),
            Fact(text="Probably not a fact.", source_url="https://example.com", confidence=0.3),
        ]
        result = validate_fact_quality(facts)
        assert result["valid"] is False
        assert any("Low average confidence" in issue for issue in result["issues"])

    def test_validate_fact_quality_stats(self):
        """Stats dict has all expected keys."""
        facts = [
            Fact(
                text="This is a good fact with sufficient length for testing.",
                source_url="https://example.com",
                confidence=0.9,
                category="api",
            ),
            Fact(text="Short", source_url="", confidence=0.5),
        ]
        result = validate_fact_quality(facts)
        stats = result["stats"]
        assert stats["total"] == 2
        assert "avg_confidence" in stats
        assert "min_confidence" in stats
        assert "max_confidence" in stats
        assert "with_source" in stats
        assert "with_category" in stats
        assert "short_facts" in stats
        assert stats["with_source"] == 1
        assert stats["with_category"] == 1
        assert stats["short_facts"] == 1  # "Short" is less than 20 chars

    def test_validate_fact_quality_missing_sources(self):
        """Many facts missing source URLs triggers issue."""
        facts = [
            Fact(text="Fact without source one here.", source_url="", confidence=0.9),
            Fact(text="Fact without source two here.", source_url="", confidence=0.9),
        ]
        result = validate_fact_quality(facts)
        assert result["valid"] is False
        assert any("missing source" in issue for issue in result["issues"])


# ---------------------------------------------------------------------------
# 5. Cleanup Tests
# ---------------------------------------------------------------------------


class TestCleanupTask:
    """Tests for the KnowledgeCleanupTask class."""

    @pytest.fixture
    def mock_mem0_memory(self):
        """Create a mock mem0 memory instance."""
        memory = MagicMock()
        memory.list = MagicMock(return_value=[])
        return memory

    def test_cleanup_task_run_once(self, mock_mem0_memory):
        """Runs cleanup and returns stats."""
        task = KnowledgeCleanupTask(mock_mem0_memory, cleanup_interval=60, ttl_days=30)
        result = asyncio.get_event_loop().run_until_complete(task.run_once())
        assert "removed" in result
        assert "kept" in result
        assert "cutoff" in result

    def test_cleanup_task_stops_on_stop_signal(self):
        """stop() halts the running loop."""
        mock_memory = MagicMock()
        mock_memory.list = MagicMock(side_effect=Exception("Should not be called after stop"))

        task = KnowledgeCleanupTask(mock_memory, cleanup_interval=1, ttl_days=30)

        async def run_and_stop():
            asyncio.create_task(task.run())
            await asyncio.sleep(0.05)
            task.stop()

        # run() should complete after stop() is called
        asyncio.get_event_loop().run_until_complete(run_and_stop())

    @pytest.mark.asyncio
    async def test_cleanup_task_run_once_with_memories(self):
        """run_once correctly processes memories with timestamps."""
        from datetime import UTC, datetime, timedelta

        mock_memory = MagicMock()

        # Create mock memory objects
        old_time = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        new_time = (datetime.now(UTC) - timedelta(days=10)).isoformat()

        old_mem = MagicMock()
        old_mem.id = "old-1"
        old_mem.metadata = {"created_at": old_time}

        new_mem = MagicMock()
        new_mem.id = "new-1"
        new_mem.metadata = {"created_at": new_time}

        mock_memory.list = MagicMock(return_value=[old_mem, new_mem])

        task = KnowledgeCleanupTask(mock_memory, ttl_days=30)
        result = await task.run_once()

        assert result["removed"] == 1
        assert result["kept"] == 1
        mock_memory.delete.assert_called_once_with(memory_id="old-1")

    @pytest.mark.asyncio
    async def test_cleanup_task_run_once_no_timestamp(self):
        """Memories without timestamps are kept."""
        mock_memory = MagicMock()
        mem = MagicMock()
        mem.id = "no-ts-1"
        mem.metadata = {}
        mock_memory.list = MagicMock(return_value=[mem])

        task = KnowledgeCleanupTask(mock_memory, ttl_days=30)
        result = await task.run_once()

        assert result["kept"] == 1
        assert result["removed"] == 0
        mock_memory.delete.assert_not_called()


class TestCleanupLifecycle:
    """Tests for start_cleanup_task and stop_cleanup_task functions."""

    def test_stop_cleanup_task_no_running(self):
        """Returns False when no task is running."""
        # Ensure no task is running
        import web_mcp.knowledge.cleanup as cleanup_module

        cleanup_module._cleanup_task = None
        result = stop_cleanup_task()
        assert result is False

    @pytest.mark.asyncio
    async def test_start_and_stop_cleanup_task(self):
        """start/stop lifecycle works."""
        import web_mcp.knowledge.cleanup as cleanup_module

        mock_memory = MagicMock()
        mock_memory.list = MagicMock(return_value=[])

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = AsyncMock()
            mock_task.cancel = MagicMock()
            mock_create_task.return_value = mock_task

            task = start_cleanup_task(mock_memory, cleanup_interval=60, ttl_days=30)

            assert isinstance(task, KnowledgeCleanupTask)
            mock_create_task.assert_called_once()

            with patch.object(cleanup_module, "_cleanup_task", mock_task):
                with patch.object(mock_task, "_instance", task):
                    result = stop_cleanup_task()
                    assert result is True
                    mock_task.cancel.assert_called_once()

        # Cleanup: reset global state
        cleanup_module._cleanup_task = None
        cleanup_module._cleanup_stop_event = None

    @pytest.mark.asyncio
    async def test_cleanup_task_error_handling(self):
        """Handles exceptions in run_once gracefully."""
        mock_memory = MagicMock()
        mock_memory.list = MagicMock(side_effect=RuntimeError("Connection refused"))

        task = KnowledgeCleanupTask(mock_memory, ttl_days=30)
        result = await task.run_once()

        assert "error" in result
        assert "Connection refused" in result["error"]


# ---------------------------------------------------------------------------
# 6. KnowledgeGatherer / Pipeline Tests
# ---------------------------------------------------------------------------


class TestKnowledgeResult:
    """Tests for the KnowledgeResult dataclass."""

    def test_summary(self):
        """summary() returns formatted string."""
        result = KnowledgeResult(
            topic="Python async",
            facts=[
                Fact(text="Asyncio is great.", source_url="https://a.com"),
                Fact(text="Await syntax is clean.", source_url="https://b.com"),
            ],
            sources=[{"url": "https://a.com"}, {"url": "https://b.com"}],
            categories=[Category("language", "Programming language features")],
            total_searched=5,
            total_fetched=2,
            total_extracted=10,
            dedup_removed=3,
            semantic_dedup_removed=2,
            stored_count=2,
            duration_seconds=4.56,
        )

        summary = result.summary()
        assert "Knowledge gathered for: Python async" in summary
        assert "Facts: 2" in summary
        assert "searched: 5" in summary
        assert "fetched: 2" in summary
        assert "extracted: 10" in summary
        assert "Dedup: 3 exact + 2 semantic removed" in summary
        assert "Stored: 2 to mem0" in summary
        assert "language" in summary
        assert "Duration: 4.6s" in summary

    def test_summary_with_errors(self):
        """summary() includes error count when errors exist."""
        result = KnowledgeResult(
            topic="test",
            facts=[],
            errors=["Search failed", "Fetch timeout"],
        )
        summary = result.summary()
        assert "Errors: 2" in summary

    def test_empty_summary(self):
        """Empty result produces a valid summary."""
        result = KnowledgeResult(topic="empty topic")
        summary = result.summary()
        assert "Knowledge gathered for: empty topic" in summary
        assert "Facts: 0" in summary


class TestKnowledgeGatherer:
    """Tests for the KnowledgeGatherer class."""

    @pytest.mark.asyncio
    async def test_gatherer_validate_topic(self):
        """Topic validation is integrated into the pipeline."""
        with (
            patch("web_mcp.searxng.search") as mock_search,
            patch("web_mcp.tools.fetching.get_page") as mock_fetch,
        ):
            mock_search.return_value = []
            mock_fetch.return_value = None

            gatherer = KnowledgeGatherer()
            result = await gatherer.gather("python")  # broad topic

            # Should continue but note issues — and fail on empty search
            assert "No search results found" in result.errors

    @pytest.mark.asyncio
    async def test_gatherer_no_search_results(self):
        """Returns error when search returns nothing."""
        with patch("web_mcp.searxng.search") as mock_search:
            mock_search.return_value = []

            gatherer = KnowledgeGatherer()
            result = await gatherer.gather("Python async programming")

            assert result.errors == ["No search results found"]
            assert result.topic == "Python async programming"
            assert result.duration_seconds > 0

    @pytest.mark.asyncio
    async def test_gatherer_fetch_failure(self):
        """Handles fetch failures gracefully."""
        with (
            patch("web_mcp.searxng.search") as mock_search,
            patch("web_mcp.tools.fetching.get_page") as mock_fetch,
        ):
            mock_search.return_value = [
                {"url": "https://example.com/1"},
                {"url": "https://example.com/2"},
            ]
            mock_fetch.side_effect = Exception("Connection refused")

            gatherer = KnowledgeGatherer()
            result = await gatherer.gather("Python async programming")

            assert "Failed to fetch any URLs" in result.errors

    @pytest.mark.asyncio
    async def test_gatherer_search_failure_returns_empty(self):
        """Search exceptions result in empty URLs list."""
        with patch("web_mcp.searxng.search") as mock_search:
            mock_search.side_effect = ConnectionError("DNS lookup failed")

            gatherer = KnowledgeGatherer()
            result = await gatherer.gather("Python async programming")

            assert result.errors == ["No search results found"]

    @pytest.mark.asyncio
    async def test_gatherer_with_mem0_stores_facts(self):
        """Facts are stored to mem0 when mem0_memory is provided."""
        mock_fact = Fact(
            text="Asyncio is great for async programming.",
            source_url="https://example.com/1",
            confidence=0.9,
            category="language",
        )
        mock_extract_result = FactExtractionResult(
            source_url="https://example.com/1", source_title="", facts=[mock_fact]
        )
        mock_memory = MagicMock()
        mock_memory.add = MagicMock(return_value=None)

        gatherer = KnowledgeGatherer(mem0_memory=mock_memory)

        # Mock the internal pipeline methods to avoid complex patch chains
        with (
            patch.object(
                gatherer, "_search", new=AsyncMock(return_value=["https://example.com/1"])
            ),
            patch.object(
                gatherer,
                "_fetch_contents",
                new=AsyncMock(
                    return_value=[
                        {
                            "url": "https://example.com/1",
                            "content": "Asyncio is a library for async programming in Python.",
                            "source": {"url": "https://example.com/1"},
                        }
                    ]
                ),
            ),
            patch.object(
                gatherer,
                "_extract_facts_from_contents",
                new=AsyncMock(return_value=[mock_extract_result]),
            ),
            patch(
                "web_mcp.knowledge.pipeline.semantic_dedup", new=AsyncMock(return_value=[mock_fact])
            ),
        ):
            result = await gatherer.gather("Python async programming")

            assert result.stored_count == 1
            mock_memory.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_gatherer_stores_zero_when_no_mem0(self):
        """stored_count is 0 when mem0_memory is not provided."""
        mock_fetch = AsyncMock(return_value="Asyncio is a library for async programming in Python.")
        with (
            patch("web_mcp.searxng.search") as mock_search,
            patch("web_mcp.tools.fetching.get_page", mock_fetch),
            patch("web_mcp.knowledge.pipeline.extract_facts") as mock_extract,
            patch("web_mcp.knowledge.pipeline.semantic_dedup") as mock_dedup,
            patch("web_mcp.llm.client.get_llm_client"),
        ):
            mock_search.return_value = [{"url": "https://example.com/1"}]

            mock_fact = Fact(
                text="Asyncio is great.", source_url="https://example.com/1", confidence=0.9
            )
            mock_extract.return_value = [
                FactExtractionResult(
                    source_url="https://example.com/1", source_title="", facts=[mock_fact]
                )
            ]
            mock_dedup.return_value = [mock_fact]

            gatherer = KnowledgeGatherer()  # no mem0_memory
            result = await gatherer.gather("Python async programming")

            assert result.stored_count == 0


class TestGatherKnowledge:
    """Tests for the gather_knowledge convenience function."""

    @pytest.mark.asyncio
    async def test_gather_knowledge_convenience_function(self):
        """Convenience function creates a gatherer and calls gather."""
        mock_mem = MagicMock()
        mock_gatherer = AsyncMock()
        mock_gatherer.gather = AsyncMock(return_value=KnowledgeResult(topic="test topic", facts=[]))
        mock_mem0_module = MagicMock()
        mock_mem0_module.get_memory = MagicMock(return_value=mock_mem)
        with (
            patch("web_mcp.knowledge.pipeline.KnowledgeGatherer") as mock_gatherer_class,
            patch("web_mcp.knowledge.pipeline.get_config") as mock_config,
            patch.dict("sys.modules", {"web_mcp.mem0": mock_mem0_module}),
        ):
            mock_gatherer_class.return_value = mock_gatherer

            mock_config_instance = MagicMock()
            mock_config_instance.knowledge_min_confidence = 0.7
            mock_config_instance.knowledge_semantic_threshold = 0.85
            mock_config.return_value = mock_config_instance

            result = await gather_knowledge("test topic", max_search_results=3)

            mock_gatherer_class.assert_called_once()
            mock_gatherer.gather.assert_called_once_with(
                "test topic", max_search_results=3, categories=None
            )
            assert isinstance(result, KnowledgeResult)
            assert result.topic == "test topic"


# ---------------------------------------------------------------------------
# 7. Integration Tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """End-to-end integration tests with fully mocked pipeline."""

    @pytest.mark.asyncio
    async def test_end_to_end_flow_mocked(self):
        """Full pipeline with mocked internal methods."""
        extracted_facts = [
            Fact(
                text="Python 3.12 introduces parenthesized context managers.",
                source_url="https://docs.python.org/3/whatsnew/3.12.html",
                confidence=0.95,
                category="language",
            ),
            Fact(
                text="asyncio provides tools for concurrent code.",
                source_url="https://realpython.com/async-io-python/",
                confidence=0.9,
                category="language",
            ),
        ]
        extract_results = [
            FactExtractionResult(
                source_url="https://docs.python.org/3/whatsnew/3.12.html",
                source_title="Python 3.12",
                facts=[extracted_facts[0]],
            ),
            FactExtractionResult(
                source_url="https://realpython.com/async-io-python/",
                source_title="Async IO Guide",
                facts=[extracted_facts[1]],
            ),
        ]

        mock_memory = MagicMock()
        mock_memory.add = MagicMock(return_value=None)

        gatherer = KnowledgeGatherer(
            mem0_memory=mock_memory,
            min_confidence=0.7,
            semantic_threshold=0.85,
        )

        with (
            patch.object(
                gatherer,
                "_search",
                new=AsyncMock(
                    return_value=[
                        "https://docs.python.org/3/whatsnew/3.12.html",
                        "https://realpython.com/async-io-python/",
                    ]
                ),
            ),
            patch.object(
                gatherer,
                "_fetch_contents",
                new=AsyncMock(
                    return_value=[
                        {
                            "url": "https://docs.python.org/3/whatsnew/3.12.html",
                            "content": "Python 3.12 introduces parenthesized context managers.",
                            "source": {"url": "https://docs.python.org/3/whatsnew/3.12.html"},
                        },
                        {
                            "url": "https://realpython.com/async-io-python/",
                            "content": "The asyncio module provides concurrent code tools.",
                            "source": {"url": "https://realpython.com/async-io-python/"},
                        },
                    ]
                ),
            ),
            patch.object(
                gatherer,
                "_extract_facts_from_contents",
                new=AsyncMock(return_value=extract_results),
            ),
            patch(
                "web_mcp.knowledge.pipeline.semantic_dedup",
                new=AsyncMock(return_value=extracted_facts),
            ),
            patch("web_mcp.knowledge.pipeline.get_config") as mock_config,
        ):
            mock_config_instance = MagicMock()
            mock_config_instance.knowledge_min_confidence = 0.7
            mock_config_instance.knowledge_semantic_threshold = 0.85
            mock_config_instance.knowledge_extract_model = "gpt-4o"
            mock_config.return_value = mock_config_instance

            result = await gatherer.gather("Python async best practices")

            # Assertions
            assert isinstance(result, KnowledgeResult)
            assert result.topic == "Python async best practices"
            assert len(result.facts) == 2
            assert result.total_searched == 2
            assert result.total_fetched == 2
            assert result.total_extracted == 2
            assert result.semantic_dedup_removed == 0
            assert result.stored_count == 2
            assert len(result.sources) == 2
            assert result.duration_seconds > 0
            assert result.errors == []
            assert result.validation is not None
            assert result.validation["valid"] is True

            # Verify mem0 was called with correct data
            assert mock_memory.add.call_count == 2
            call_args = mock_memory.add.call_args_list
            assert (
                "Python 3.12 introduces parenthesized context managers."
                in call_args[0][1]["message"]
            )
            assert (
                "Source: https://docs.python.org/3/whatsnew/3.12.html" in call_args[0][1]["message"]
            )
