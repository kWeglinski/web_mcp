"""Unit tests for fetching tools (get_page, render_html)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_mcp.extractors.base import ExtractedContent
from web_mcp.pdf_processor import PaginatedPDF, PDFExtractionError
from web_mcp.research.chunker import Chunk


def _make_mock_config(**overrides):
    config = MagicMock()
    config.request_timeout = 30
    config.max_content_length = 10485760
    config.cache_ttl = 3600
    config.request_delay_min = 0.0
    config.request_delay_max = 0.0
    config.tls_client_identifier = "chrome120"
    config.playwright_enabled = True
    config.public_url = "https://mcp.example.com"
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def _make_mock_fetched(content=b"test", content_type="text/html", url="https://example.com"):
    from web_mcp.fetcher import FetchedContent

    return FetchedContent(content=content, content_type=content_type, url=url)


def _make_extracted(text="test text", title="Test Page"):
    return ExtractedContent(
        title=title,
        author=None,
        date=None,
        language=None,
        text=text,
        url="https://example.com",
        metadata={},
    )


class TestGetPage:
    def test_get_page_negative_page(self):
        from web_mcp.tools.fetching import get_page

        result = asyncio.get_event_loop().run_until_complete(
            get_page("https://example.com", page=-1)
        )
        assert result == "Error: page parameter must be non-negative"

    @pytest.mark.asyncio
    async def test_get_page_fetch_success(self):

        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_default_extractor") as mock_extractor_getter,
            patch("web_mcp.tools.fetching._get_pdf_cache"),
        ):
            mock_fetch.return_value = _make_mock_fetched(b"<html><body>Test</body></html>")
            mock_extractor = MagicMock()
            mock_extractor.extract = AsyncMock(return_value=_make_extracted("extracted text"))
            mock_extractor_getter.return_value = mock_extractor

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com")
            assert result == "extracted text"

    @pytest.mark.asyncio
    async def test_get_page_fetch_fails_no_playwright(self):
        from web_mcp.fetcher import FetchError

        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching.get_config") as mock_config_getter,
        ):
            mock_fetch.side_effect = FetchError("Connection refused")
            mock_config = _make_mock_config(playwright_enabled=False)
            mock_config_getter.return_value = mock_config

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com")
            assert "Error fetching URL" in result

    @pytest.mark.asyncio
    async def test_get_page_fetch_fails_both_methods(self):
        from web_mcp.fetcher import FetchError
        from web_mcp.playwright_fetcher import PlaywrightFetchError

        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching.get_config") as mock_config_getter,
            patch("web_mcp.playwright_fetcher.fetch_with_playwright_cached") as mock_pw,
        ):
            mock_fetch.side_effect = FetchError("Connection refused")
            mock_pw.side_effect = PlaywrightFetchError("Browser failed")
            mock_config = _make_mock_config(playwright_enabled=True)
            mock_config_getter.return_value = mock_config

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com")
            assert "both failed" in result

    @pytest.mark.asyncio
    async def test_get_page_pdf_content(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_pdf_cache") as mock_cache_getter,
            patch("web_mcp.tools.fetching.pdf_to_markdown") as mock_pdf_md,
            patch("web_mcp.tools.fetching.paginate_markdown") as mock_paginate,
        ):
            mock_fetch.return_value = _make_mock_fetched(
                b"%PDF-1.4 fake pdf", content_type="application/pdf"
            )
            mock_cache = MagicMock()
            mock_cache.get.return_value = None
            mock_cache_getter.return_value = mock_cache
            mock_pdf_md.return_value = "PDF text content"
            mock_paginate.return_value = PaginatedPDF(
                current_page=0, total_pages=1, content="PDF text content"
            )

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com")
            assert result == "PDF text content"

    @pytest.mark.asyncio
    async def test_get_page_pdf_cache_hit(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_pdf_cache") as mock_cache_getter,
            patch("web_mcp.tools.fetching.paginate_markdown") as mock_paginate,
        ):
            mock_fetch.return_value = _make_mock_fetched(
                b"%PDF-1.4 fake pdf", content_type="application/pdf"
            )
            mock_cache = MagicMock()
            mock_cache.get.return_value = "cached pdf text"
            mock_cache_getter.return_value = mock_cache
            mock_paginate.return_value = PaginatedPDF(
                current_page=0, total_pages=1, content="cached pdf text"
            )

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com")
            assert result == "cached pdf text"

    @pytest.mark.asyncio
    async def test_get_page_pdf_extraction_error(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_pdf_cache") as mock_cache_getter,
            patch("web_mcp.tools.fetching.pdf_to_markdown") as mock_pdf_md,
        ):
            mock_fetch.return_value = _make_mock_fetched(
                b"%PDF-1.4 corrupt", content_type="application/pdf"
            )
            mock_cache = MagicMock()
            mock_cache.get.return_value = None
            mock_cache_getter.return_value = mock_cache
            mock_pdf_md.side_effect = PDFExtractionError("Corrupt PDF")

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com")
            assert "Error processing PDF" in result

    @pytest.mark.asyncio
    async def test_get_page_pdf_multi_page(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_pdf_cache") as mock_cache_getter,
            patch("web_mcp.tools.fetching.paginate_markdown") as mock_paginate,
        ):
            mock_fetch.return_value = _make_mock_fetched(
                b"%PDF-1.4", content_type="application/pdf"
            )
            mock_cache = MagicMock()
            mock_cache.get.return_value = "page 1 text"
            mock_cache_getter.return_value = mock_cache
            mock_paginate.return_value = PaginatedPDF(
                current_page=0, total_pages=3, content="page 1"
            )

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com")
            assert "CHUNK 0/3" in result
            assert "Use page=1 for more content" in result

    @pytest.mark.asyncio
    async def test_get_page_pdf_last_page(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_pdf_cache") as mock_cache_getter,
            patch("web_mcp.tools.fetching.paginate_markdown") as mock_paginate,
        ):
            mock_fetch.return_value = _make_mock_fetched(
                b"%PDF-1.4", content_type="application/pdf"
            )
            mock_cache = MagicMock()
            mock_cache.get.return_value = "page 3 text"
            mock_cache_getter.return_value = mock_cache
            mock_paginate.return_value = PaginatedPDF(
                current_page=2, total_pages=3, content="page 3"
            )

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com")
            assert "Final chunk" in result

    @pytest.mark.asyncio
    async def test_get_page_with_query_bm25(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_default_extractor") as mock_extractor_getter,
            patch("web_mcp.tools.fetching._rank_chunks_with_bm25") as mock_bm25,
        ):
            mock_fetch.return_value = _make_mock_fetched(b"<html><body>Test</body></html>")
            mock_extractor = MagicMock()
            mock_extractor.extract = AsyncMock(
                return_value=_make_extracted("some text content here")
            )
            mock_extractor_getter.return_value = mock_extractor
            mock_bm25.return_value = "ranked chunk text"

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com", query="test query")
            assert result == "Title: Test Page\n\nranked chunk text"

    @pytest.mark.asyncio
    async def test_get_page_extractor_error(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_default_extractor") as mock_extractor_getter,
        ):
            mock_fetch.return_value = _make_mock_fetched(b"<html><body>Test</body></html>")
            mock_extractor = MagicMock()
            mock_extractor.extract = AsyncMock(side_effect=Exception("Extraction failed"))
            mock_extractor_getter.return_value = mock_extractor

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com")
            assert "Error extracting content" in result

    @pytest.mark.asyncio
    async def test_get_page_empty_extraction(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_default_extractor") as mock_extractor_getter,
        ):
            mock_fetch.return_value = _make_mock_fetched(b"<html><body>Test</body></html>")
            mock_extractor = MagicMock()
            mock_extractor.extract = AsyncMock(
                return_value=ExtractedContent(
                    title="Test",
                    author=None,
                    date=None,
                    language=None,
                    text="",
                    url="https://example.com",
                    metadata={},
                )
            )
            mock_extractor_getter.return_value = mock_extractor

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com", query="test query")
            assert result == "No content extracted from page"

    @pytest.mark.asyncio
    async def test_get_page_readability_extractor(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.extractors.readability.ReadabilityExtractor") as mock_reader_class,
        ):
            mock_fetch.return_value = _make_mock_fetched(b"<html><body>Test</body></html>")
            mock_extractor = MagicMock()
            mock_extractor.extract = AsyncMock(
                return_value=ExtractedContent(
                    title="Test",
                    author=None,
                    date=None,
                    language=None,
                    text="readable text",
                    url="https://example.com",
                    metadata={},
                )
            )
            mock_reader_class.return_value = mock_extractor

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com", extractor="readability")
            assert result == "readable text"

    @pytest.mark.asyncio
    async def test_get_page_custom_extractor(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_custom_extractor") as mock_custom_getter,
        ):
            mock_fetch.return_value = _make_mock_fetched(b"<html><body>Test</body></html>")
            mock_extractor = MagicMock()
            mock_extractor.extract = AsyncMock(
                return_value=ExtractedContent(
                    title="Test",
                    author=None,
                    date=None,
                    language=None,
                    text="custom text",
                    url="https://example.com",
                    metadata={},
                )
            )
            mock_custom_getter.return_value = mock_extractor

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com", extractor="custom")
            assert result == "custom text"

    @pytest.mark.asyncio
    async def test_get_page_default_extractor_used(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_default_extractor") as mock_default_getter,
        ):
            mock_fetch.return_value = _make_mock_fetched(b"<html><body>Test</body></html>")
            mock_extractor = MagicMock()
            mock_extractor.extract = AsyncMock(
                return_value=ExtractedContent(
                    title="Test",
                    author=None,
                    date=None,
                    language=None,
                    text="default text",
                    url="https://example.com",
                    metadata={},
                )
            )
            mock_default_getter.return_value = mock_extractor

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com", extractor="trafilatura")
            assert result == "default text"

    @pytest.mark.asyncio
    async def test_get_page_pdf_query_bm25(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_pdf_cache") as mock_cache_getter,
            patch("web_mcp.tools.fetching.pdf_to_markdown") as mock_pdf_md,
            patch("web_mcp.tools.fetching._rank_chunks_with_bm25") as mock_bm25,
        ):
            mock_fetch.return_value = _make_mock_fetched(
                b"%PDF-1.4", content_type="application/pdf"
            )
            mock_cache = MagicMock()
            mock_cache.get.return_value = None
            mock_cache_getter.return_value = mock_cache
            mock_pdf_md.return_value = "pdf full text content"
            mock_bm25.return_value = "ranked pdf chunks"

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com", query="pdf query")
            assert result == "ranked pdf chunks"

    @pytest.mark.asyncio
    async def test_get_page_no_title(self):
        with (
            patch("web_mcp.tools.fetching.fetch_url_with_metadata") as mock_fetch,
            patch("web_mcp.tools.fetching._get_default_extractor") as mock_extractor_getter,
            patch("web_mcp.tools.fetching._rank_chunks_with_bm25") as mock_bm25,
        ):
            mock_fetch.return_value = _make_mock_fetched(b"<html><body>Test</body></html>")
            mock_extractor = MagicMock()
            mock_extractor.extract = AsyncMock(
                return_value=ExtractedContent(
                    title=None,
                    author=None,
                    date=None,
                    language=None,
                    text="some text",
                    url="https://example.com",
                    metadata={},
                )
            )
            mock_extractor_getter.return_value = mock_extractor
            mock_bm25.return_value = "ranked text"

            from web_mcp.tools.fetching import get_page

            result = await get_page("https://example.com", query="test")
            assert result.startswith("ranked text")


class TestRenderHtml:
    @pytest.mark.asyncio
    async def test_render_html_success(self):
        from web_mcp.tools.fetching import render_html

        with (
            patch("web_mcp.tools.fetching.get_config") as mock_config,
            patch("web_mcp.tools.fetching.get_content_store") as mock_store_getter,
            patch("web_mcp.tools.fetching.increment_request_count"),
        ):
            mock_config.return_value = _make_mock_config(public_url="https://mcp.example.com")
            mock_store = MagicMock()
            mock_store.store.return_value = ("abc123", "token456")
            mock_store_getter.return_value = mock_store

            result = await render_html("<h1>Hello</h1>")
            assert "https://mcp.example.com/c/abc123?token=token456" == result

    @pytest.mark.asyncio
    async def test_render_html_no_public_url(self):
        from web_mcp.tools.fetching import render_html

        with (
            patch("web_mcp.tools.fetching.get_config") as mock_config,
            patch("web_mcp.tools.fetching.increment_request_count"),
        ):
            mock_config.return_value = _make_mock_config(public_url=None)

            result = await render_html("<h1>Hello</h1>")
            assert "WEB_MCP_PUBLIC_URL not configured" in result

    @pytest.mark.asyncio
    async def test_render_html_wraps_content(self):
        from web_mcp.tools.fetching import render_html

        with (
            patch("web_mcp.tools.fetching.get_config") as mock_config,
            patch("web_mcp.tools.fetching.get_content_store") as mock_store_getter,
            patch("web_mcp.tools.fetching.increment_request_count"),
        ):
            mock_config.return_value = _make_mock_config(public_url="https://mcp.example.com")
            mock_store = MagicMock()
            mock_store.store.return_value = ("abc123", "token456")
            mock_store_getter.return_value = mock_store

            await render_html("<p>Body content</p>")

            stored_content = mock_store.store.call_args[0][0]
            assert "<!DOCTYPE html>" in stored_content
            assert "<p>Body content</p>" in stored_content
            assert "Content-Security-Policy" in stored_content


class TestRankChunksWithBM25:
    @pytest.mark.asyncio
    async def test_rank_chunks_with_bm25(self):
        from web_mcp.tools.fetching import _rank_chunks_with_bm25

        with (
            patch("web_mcp.tools.fetching.chunk_text") as mock_chunk,
            patch("web_mcp.tools.fetching.BM25") as mock_bm25_class,
        ):
            chunk1 = Chunk(
                text="first chunk text",
                source_url="https://example.com",
                source_title="Test",
                index=0,
            )
            chunk2 = Chunk(
                text="second chunk text",
                source_url="https://example.com",
                source_title="Test",
                index=1,
            )
            mock_chunk.return_value = [chunk1, chunk2]

            mock_bm25 = MagicMock()
            mock_bm25_class.return_value = mock_bm25
            mock_bm25.rank.return_value = [
                ({"text": "first chunk text", "chunk": chunk1}, 0.9),
                ({"text": "second chunk text", "chunk": chunk2}, 0.7),
            ]

            result = _rank_chunks_with_bm25("some text", "https://example.com", "Test", "query")
            assert "first chunk text" in result

    @pytest.mark.asyncio
    async def test_rank_chunks_empty_fallback(self):
        from web_mcp.tools.fetching import _rank_chunks_with_bm25

        with patch("web_mcp.tools.fetching.chunk_text") as mock_chunk:
            mock_chunk.return_value = []

            result = _rank_chunks_with_bm25("short text", "https://example.com", "Test", "query")
            assert result == "short text"


class TestExtractors:
    @pytest.mark.asyncio
    async def test_lazy_default_extractor(self):
        from web_mcp.tools.fetching import _get_default_extractor

        with patch("web_mcp.extractors.trafilatura.TrafilaturaExtractor") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            result = _get_default_extractor()
            assert result is mock_instance
            mock_class.assert_called_once()

            result2 = _get_default_extractor()
            assert result2 is result

    @pytest.mark.asyncio
    async def test_lazy_custom_extractor(self):
        from web_mcp.tools.fetching import _get_custom_extractor

        with patch("web_mcp.extractors.custom.CustomSelectorExtractor") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            result = _get_custom_extractor()
            assert result is mock_instance
            mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_lazy_pdf_cache(self):
        from web_mcp.tools.fetching import _get_pdf_cache

        with patch("web_mcp.tools.fetching.PDFCache") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            result = _get_pdf_cache()
            assert result is mock_instance
            mock_class.assert_called_once()


class TestHTMLWrapper:
    def test_html_wrapper_template_contains_expected_tags(self):
        from web_mcp.tools.fetching import HTML_WRAPPER_TEMPLATE

        assert "<!DOCTYPE html>" in HTML_WRAPPER_TEMPLATE
        assert "Content-Security-Policy" in HTML_WRAPPER_TEMPLATE
        assert "{content}" in HTML_WRAPPER_TEMPLATE


class TestConstants:
    def test_bm25_constants(self):
        from web_mcp.tools.fetching import (
            BM25_CHUNK_OVERLAP,
            BM25_CHUNK_SIZE,
            BM25_TOP_CHUNKS,
            MAX_FALLBACK_HTML_LENGTH,
            MAX_FALLBACK_TEXT_LENGTH,
        )

        assert BM25_CHUNK_SIZE == 500
        assert BM25_CHUNK_OVERLAP == 50
        assert BM25_TOP_CHUNKS == 5
        assert MAX_FALLBACK_TEXT_LENGTH == 10000
        assert MAX_FALLBACK_HTML_LENGTH == 2000
