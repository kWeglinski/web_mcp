"""Unit tests for PDF processing utilities."""

import time
from unittest.mock import MagicMock, patch

import pytest

from web_mcp.pdf_processor import (
    MAX_PDF_SIZE,
    PaginatedPDF,
    PDFCache,
    PDFExtractionError,
    _read_pdf_pages,
    _read_pdf_pages_pypdf,
    extract_text_from_pdf,
    is_pdf_content_type,
    paginate_markdown,
    pdf_to_markdown,
)


class TestIsPdfContentType:
    def test_application_pdf(self):
        assert is_pdf_content_type("application/pdf") is True

    def test_application_pdf_with_charset(self):
        assert is_pdf_content_type("application/pdf; charset=utf-8") is True

    def test_uppercase(self):
        assert is_pdf_content_type("APPLICATION/PDF") is True

    def test_with_whitespace(self):
        assert is_pdf_content_type("  application/pdf  ") is True

    def test_empty_string(self):
        assert is_pdf_content_type("") is False

    def test_none(self):
        assert is_pdf_content_type("application/pdf; charset=utf-8") is True

    def test_pdf_text(self):
        assert is_pdf_content_type("application/pdf") is True

    def test_not_pdf(self):
        assert is_pdf_content_type("text/html") is False

    def test_not_pdf_json(self):
        assert is_pdf_content_type("application/json") is False


class TestExtractTextFromPdf:
    @patch("web_mcp.pdf_processor._read_pdf_pages")
    def test_extract_text_joins_pages(self, mock_read):
        mock_read.return_value = ["Page 1 text", "Page 2 text"]
        result = extract_text_from_pdf(b"fake pdf bytes")
        assert result == "Page 1 text\n\nPage 2 text"
        mock_read.assert_called_once_with(b"fake pdf bytes")

    @patch("web_mcp.pdf_processor._read_pdf_pages")
    def test_extract_text_empty_pages(self, mock_read):
        mock_read.return_value = []
        result = extract_text_from_pdf(b"fake pdf bytes")
        assert result == ""

    def test_extract_text_exceeds_max_size(self):
        oversized = b"x" * (MAX_PDF_SIZE + 1)
        with pytest.raises(PDFExtractionError, match="exceeds maximum size limit"):
            extract_text_from_pdf(oversized)

    @patch("web_mcp.pdf_processor._read_pdf_pages")
    def test_extract_text_pypdfium2_fallback(self, mock_read):
        mock_read.return_value = ["Fallback page"]
        result = extract_text_from_pdf(b"fake pdf bytes")
        assert result == "Fallback page"


class TestPdfToMarkdown:
    @patch("web_mcp.pdf_processor._read_pdf_pages")
    def test_pdf_to_markdown_single_page(self, mock_read):
        mock_read.return_value = ["Single page content"]
        result = pdf_to_markdown(b"fake pdf bytes", "https://example.com/doc.pdf")
        assert "# PDF: https://example.com/doc.pdf" in result
        assert "## PDF Page 1" in result
        assert "Single page content" in result

    @patch("web_mcp.pdf_processor._read_pdf_pages")
    def test_pdf_to_markdown_multiple_pages(self, mock_read):
        mock_read.return_value = ["First page", "Second page", "Third page"]
        result = pdf_to_markdown(b"fake pdf bytes", "https://example.com/doc.pdf")
        assert "## PDF Page 1" in result
        assert "## PDF Page 2" in result
        assert "## PDF Page 3" in result
        assert "First page" in result
        assert "Second page" in result
        assert "Third page" in result

    def test_pdf_to_markdown_exceeds_max_size(self):
        oversized = b"x" * (MAX_PDF_SIZE + 1)
        with pytest.raises(PDFExtractionError, match="exceeds maximum size limit"):
            pdf_to_markdown(oversized, "https://example.com/doc.pdf")


class TestReadPdfPagesPypdf:
    @patch("web_mcp.pdf_processor.PdfReader")
    def test_read_pdf_pages_pypdf_success(self, mock_reader_class):
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Extracted text"
        mock_reader.pages = [mock_page]
        mock_reader_class.return_value = mock_reader

        result = _read_pdf_pages_pypdf(b"test pdf bytes")
        assert result == ["Extracted text"]
        mock_reader_class.assert_called_once()

    @patch("web_mcp.pdf_processor.PdfReader")
    def test_read_pdf_pages_pypdf_control_chars_removed(self, mock_reader_class):
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Text with\x00\x01\x02 control"
        mock_reader.pages = [mock_page]
        mock_reader_class.return_value = mock_reader

        result = _read_pdf_pages_pypdf(b"test pdf bytes")
        assert "\x00" not in result[0]
        assert "\x01" not in result[0]
        assert "\x02" not in result[0]

    @patch("web_mcp.pdf_processor.PdfReader")
    @patch("web_mcp.logging.get_logger")
    def test_read_pdf_pages_pypdf_raises_on_error(self, mock_logger, mock_reader_class):
        from pypdf.errors import PdfReadError

        mock_reader_class.side_effect = PdfReadError("Bad PDF")

        with pytest.raises(PDFExtractionError, match="Failed to read PDF"):
            _read_pdf_pages_pypdf(b"bad pdf bytes")

    @patch("web_mcp.pdf_processor.PdfReader")
    def test_read_pdf_pages_pypdf_empty_pages(self, mock_reader_class):
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = None
        mock_reader.pages = [mock_page]
        mock_reader_class.return_value = mock_reader

        result = _read_pdf_pages_pypdf(b"test pdf bytes")
        assert result == []

    @patch("web_mcp.pdf_processor.PdfReader")
    def test_read_pdf_pages_pypdf_empty_string_pages(self, mock_reader_class):
        mock_reader = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader.pages = [mock_page]
        mock_reader_class.return_value = mock_reader

        result = _read_pdf_pages_pypdf(b"test pdf bytes")
        assert result == []


class TestReadPdfPages:
    @patch("web_mcp.pdf_processor.pypdfium2")
    def test_read_pdf_pages_uses_pypdfium2(self, mock_pypdfium2):
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_textpage = MagicMock()
        mock_textpage.get_text_range.return_value = "Page text from pypdfium2"
        mock_page.get_textpage.return_value = mock_textpage
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_pypdfium2.PdfDocument.return_value = mock_doc

        result = _read_pdf_pages(b"test pdf bytes")
        assert result == ["Page text from pypdfium2"]
        mock_doc.close.assert_called_once()

    @patch("web_mcp.pdf_processor.pypdfium2")
    def test_read_pdf_pages_falls_back_to_pypdf(self, mock_pypdfium2):
        mock_pypdfium2.PdfDocument.side_effect = Exception("pypdfium2 broken")

        with patch("web_mcp.pdf_processor._read_pdf_pages_pypdf") as mock_fallback:
            mock_fallback.return_value = ["Fallback text"]
            result = _read_pdf_pages(b"test pdf bytes")
            assert result == ["Fallback text"]
            mock_fallback.assert_called_once()


class TestPaginateMarkdown:
    def test_paginate_markdown_empty_text(self):
        result = paginate_markdown("")
        assert isinstance(result, PaginatedPDF)
        assert result.content == ""
        assert result.current_page == 0
        assert result.total_pages == 1

    def test_paginate_markdown_negative_page(self):
        with pytest.raises(ValueError, match="Page must be >= 0"):
            paginate_markdown("some content", page=-1)

    def test_paginate_markdown_single_paragraph(self):
        result = paginate_markdown("Single paragraph of text", chars_per_page=1000)
        assert result.content == "Single paragraph of text"
        assert result.total_pages == 1

    def test_paginate_markdown_multiple_pages(self):
        long_text = "Para1\n\n" + "A" * 500 + "\n\n" + "Para3\n\n" + "B" * 500
        result = paginate_markdown(long_text, chars_per_page=600)
        assert result.total_pages >= 2
        assert result.current_page >= 0

    def test_paginate_markdown_page_beyond_total(self):
        result = paginate_markdown("Small content", page=100, chars_per_page=1000)
        assert result.total_pages == 1
        assert result.current_page == 0

    def test_paginate_markdown_custom_chars_per_page(self):
        text = "Para1\n\nPara2\n\nPara3"
        result = paginate_markdown(text, chars_per_page=10)
        assert result.total_pages >= 3

    def test_paginate_markdown_preserves_paragraphs(self):
        text = "First paragraph\n\nSecond paragraph\n\nThird paragraph"
        result = paginate_markdown(text, chars_per_page=5000)
        assert "First paragraph" in result.content
        assert "Second paragraph" in result.content
        assert "Third paragraph" in result.content

    def test_paginate_markdown_zero_page(self):
        result = paginate_markdown("Test content", page=0, chars_per_page=5000)
        assert result.current_page == 0

    def test_paginate_markdown_non_empty(self):
        result = paginate_markdown("Some content here", page=0, chars_per_page=5000)
        assert result.content == "Some content here"

    def test_paginate_markdown_config_used_when_no_custom(self):
        with patch("web_mcp.pdf_processor.get_config") as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.pdf_chars_per_page = 2000
            mock_config.return_value = mock_cfg
            result = paginate_markdown("Content")
            assert isinstance(result, PaginatedPDF)


class TestPDFCache:
    def test_cache_set_and_get(self):
        cache = PDFCache(ttl_seconds=60, max_entries=10)
        cache.set("https://example.com", "markdown content")
        assert cache.get("https://example.com") == "markdown content"

    def test_cache_miss_returns_none(self):
        cache = PDFCache(ttl_seconds=60, max_entries=10)
        assert cache.get("https://nonexistent.com") is None

    def test_cache_key_sanitization(self):
        cache = PDFCache(ttl_seconds=60, max_entries=10)
        url_with_null = "https://example.com\x00page"
        cache.set(url_with_null, "content")
        assert cache.get(url_with_null) == "content"

    def test_cache_key_is_hashed(self):
        cache = PDFCache(ttl_seconds=60, max_entries=10)
        long_url = "https://example.com/" + "a" * 1000
        cache.set(long_url, "content")
        key = cache._make_key(long_url)
        assert len(key) == 64  # SHA256 hex digest length

    def test_cache_eviction(self):
        cache = PDFCache(ttl_seconds=60, max_entries=3)
        cache.set("url1", "content1")
        cache.set("url2", "content2")
        cache.set("url3", "content3")
        cache.set("url4", "content4")  # Should evict url1
        assert cache.get("url1") is None
        assert cache.get("url4") == "content4"

    def test_cache_update_existing(self):
        cache = PDFCache(ttl_seconds=60, max_entries=10)
        cache.set("url1", "old content")
        cache.set("url1", "new content")
        assert len(cache) == 1
        assert cache.get("url1") == "new content"

    def test_cache_len(self):
        cache = PDFCache(ttl_seconds=60, max_entries=10)
        assert len(cache) == 0
        cache.set("url1", "content1")
        assert len(cache) == 1
        cache.set("url2", "content2")
        assert len(cache) == 2

    def test_cache_expired_entry(self):
        cache = PDFCache(ttl_seconds=0, max_entries=10)
        cache.set("url1", "content1")
        time.sleep(0.01)
        assert cache.get("url1") is None

    def test_cache_clear_expired(self):
        cache = PDFCache(ttl_seconds=60, max_entries=10)
        cache.set("url1", "content1")
        cache.set("url2", "content2")
        hashed_url1 = cache._make_key("url1")
        cache._cache[hashed_url1] = ("expired", time.time() - 1000)
        cache.clear_expired()
        assert hashed_url1 not in cache._cache
        assert cache.get("url2") == "content2"

    def test_cache_max_entries_default(self):
        cache = PDFCache()
        assert cache._max_entries == 50
        assert cache._ttl == 3600

    def test_cache_ttl_default(self):
        cache = PDFCache(max_entries=10)
        assert cache._ttl == 3600

    def test_cache_moves_to_end_on_get(self):
        cache = PDFCache(ttl_seconds=60, max_entries=3)
        cache.set("url1", "content1")
        cache.set("url2", "content2")
        cache.set("url3", "content3")
        cache.get("url1")  # Access url1 to make it recently used
        cache.set("url4", "content4")  # Should evict url2, not url1
        assert cache.get("url1") == "content1"
        assert cache.get("url2") is None
