"""Unit tests for the chunker module."""

from web_mcp.research.chunker import (
    Chunk,
    chunk_text,
    merge_small_chunks,
)


class TestChunkText:
    """Tests for chunk_text function."""

    def test_chunk_text_basic(self):
        """Test basic chunking."""
        text = "This is a test. This is another sentence. And one more."
        chunks = chunk_text(text, "https://example.com", "Test Page", chunk_size=50)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert isinstance(chunk, Chunk)
            assert chunk.source_url == "https://example.com"
            assert chunk.source_title == "Test Page"

    def test_chunk_text_empty(self):
        """Test empty string."""
        chunks = chunk_text("", "https://example.com", "Test")
        assert chunks == []

    def test_chunk_text_none(self):
        """Test None input."""
        chunks = chunk_text(None, "https://example.com", "Test")
        assert chunks == []

    def test_chunk_text_single_sentence(self):
        """Test single sentence."""
        text = "This is a test."
        chunks = chunk_text(text, "https://example.com", "Test Page")

        assert len(chunks) == 1
        assert chunks[0].text == "This is a test."

    def test_chunk_text_multiple_chunks(self):
        """Test multiple chunks."""
        # Create text that will be split into multiple chunks
        text = ". ".join(["This is a test sentence"] * 10)
        chunks = chunk_text(text, "https://example.com", "Test Page", chunk_size=50)

        assert len(chunks) > 1

    def test_chunk_text_with_overlap(self):
        """Test chunking with overlap."""
        text = "First. Second. Third. Fourth."
        chunks = chunk_text(text, "https://example.com", "Test Page", chunk_size=30, overlap=10)

        assert len(chunks) >= 1


class TestMergeSmallChunks:
    """Tests for merge_small_chunks function."""

    def test_merge_small_chunks_basic(self):
        """Test merging small chunks."""
        chunks = [
            Chunk(text="Short", source_url="url1", source_title="Title1", index=0),
            Chunk(text="Short", source_url="url1", source_title="Title1", index=1),
            Chunk(text="This is a longer chunk", source_url="url1", source_title="Title1", index=2),
        ]

        merged = merge_small_chunks(chunks, min_size=10)

        # Should have fewer chunks after merging
        assert len(merged) <= len(chunks)

    def test_merge_small_chunks_empty(self):
        """Test empty list."""
        merged = merge_small_chunks([])
        assert merged == []

    def test_merge_small_chunks_no_merge_needed(self):
        """Test when no merging is needed."""
        chunks = [
            Chunk(text="This is a long chunk", source_url="url1", source_title="Title1", index=0),
            Chunk(text="Another long chunk", source_url="url1", source_title="Title1", index=1),
        ]

        merged = merge_small_chunks(chunks, min_size=20)

        # Should keep all chunks since they're large enough
        assert len(merged) == 2

    def test_merge_small_chunks_different_urls(self):
        """Test that chunks from different URLs are not merged."""
        chunks = [
            Chunk(text="Short", source_url="url1", source_title="Title1", index=0),
            Chunk(text="Short", source_url="url2", source_title="Title2", index=1),
        ]

        merged = merge_small_chunks(chunks, min_size=20)

        # Should not merge chunks from different URLs
        assert len(merged) == 2

    def test_merge_small_chunks_merges_adjacent(self):
        """Test merging of adjacent small chunks."""
        chunks = [
            Chunk(text="Short", source_url="url1", source_title="Title1", index=0),
            Chunk(text="Short", source_url="url1", source_title="Title1", index=1),
            Chunk(text="Short", source_url="url1", source_title="Title1", index=2),
        ]

        merged = merge_small_chunks(chunks, min_size=15)

        # Should merge into one chunk
        assert len(merged) == 1
        assert "Short" in merged[0].text


class TestChunkDataclass:
    """Tests for Chunk dataclass."""

    def test_chunk_fields(self):
        """Test Chunk has all required fields."""
        chunk = Chunk(
            text="Test text",
            source_url="https://example.com",
            source_title="Test Title",
            index=0,
        )

        assert chunk.text == "Test text"
        assert chunk.source_url == "https://example.com"
        assert chunk.source_title == "Test Title"
        assert chunk.index == 0
