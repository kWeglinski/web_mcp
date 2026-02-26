"""Unit tests for the citations module."""

import pytest

from web_mcp.research.citations import (
    Source,
    extract_urls_from_text,
    format_sources,
    build_context_with_citations,
    renumber_citations,
)


class TestExtractUrlsFromText:
    """Tests for extract_urls_from_text function."""

    def test_extract_urls_basic(self):
        """Test basic URL extraction."""
        text = "Check out https://example.com for more info."
        urls = extract_urls_from_text(text)
        
        assert "https://example.com" in urls

    def test_extract_urls_multiple(self):
        """Test multiple URL extraction."""
        text = "Visit https://example.com or http://test.org for more info."
        urls = extract_urls_from_text(text)
        
        assert len(urls) >= 2
        assert "https://example.com" in urls
        assert "http://test.org" in urls

    def test_extract_urls_empty(self):
        """Test empty string."""
        urls = extract_urls_from_text("")
        assert urls == []

    def test_extract_urls_none(self):
        """Test None input."""
        urls = extract_urls_from_text(None)
        assert urls == []

    def test_extract_urls_no_urls(self):
        """Test text without URLs."""
        text = "This is just regular text with no URLs."
        urls = extract_urls_from_text(text)
        assert urls == []


class TestFormatSources:
    """Tests for format_sources function."""

    def test_format_sources_basic(self):
        """Test basic source formatting."""
        sources = [
            Source(index=1, url="https://example.com", title="Example"),
        ]
        
        result = format_sources(sources)
        
        assert "[1]" in result
        assert "Example" in result
        assert "https://example.com" in result

    def test_format_sources_empty(self):
        """Test empty list."""
        sources = []
        result = format_sources(sources)
        
        assert result == ""

    def test_format_sources_multiple(self):
        """Test multiple sources."""
        sources = [
            Source(index=1, url="https://example.com", title="Example"),
            Source(index=2, url="https://test.org", title="Test"),
        ]
        
        result = format_sources(sources)
        
        assert "[1]" in result
        assert "[2]" in result

    def test_format_sources_no_url(self):
        """Test source without URL."""
        sources = [
            Source(index=1, url=None, title="Example"),
        ]
        
        result = format_sources(sources)
        
        assert "[1]" in result
        assert "Example" in result


class TestBuildContextWithCitations:
    """Tests for build_context_with_citations function."""

    def test_build_context_basic(self):
        """Test basic context building."""
        from web_mcp.research.chunker import Chunk
        
        chunks = [
            (Chunk(
                text="First chunk",
                source_url="https://example.com",
                source_title="Example",
                index=0,
            ), 0.9),
        ]
        
        context, sources = build_context_with_citations(chunks)
        
        assert "[1]" in context
        assert "First chunk" in context
        assert len(sources) == 1

    def test_build_context_empty(self):
        """Test empty list."""
        context, sources = build_context_with_citations([])
        
        assert context == ""
        assert sources == []

    def test_build_context_max_chars(self):
        """Test max characters limit."""
        from web_mcp.research.chunker import Chunk
        
        chunks = [
            (Chunk(
                text="A" * 100,
                source_url="https://example.com",
                source_title="Example",
                index=0,
            ), 0.9),
        ]
        
        context, sources = build_context_with_citations(chunks, max_context_chars=50)
        
        # Should be truncated
        assert len(context) <= 50

    def test_build_context_deduplicates_urls(self):
        """Test that duplicate URLs are deduplicated."""
        from web_mcp.research.chunker import Chunk
        
        chunks = [
            (Chunk(
                text="First",
                source_url="https://example.com",
                source_title="Example",
                index=0,
            ), 0.9),
            (Chunk(
                text="Second",
                source_url="https://example.com",
                source_title="Example",
                index=1,
            ), 0.8),
        ]
        
        context, sources = build_context_with_citations(chunks)
        
        # Should have only one source
        assert len(sources) == 1


class TestRenumberCitations:
    """Tests for renumber_citations function."""

    def test_renumber_citations_basic(self):
        """Test basic citation renumbering."""
        text = "This is a test [1] with citations."
        sources = [
            Source(index=1, url="https://example.com", title="Example"),
        ]
        
        result = renumber_citations(text, sources)
        
        assert "[1]" in result

    def test_renumber_citations_empty(self):
        """Test empty text."""
        result = renumber_citations("", [])
        assert result == ""

    def test_renumber_citations_no_citations(self):
        """Test text without citations."""
        text = "This is just regular text."
        result = renumber_citations(text, [])
        
        assert result == "This is just regular text."
