"""PDF processing utilities."""

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from time import time
from typing import Final

from pypdf import PdfReader
from pypdf.errors import DependencyError, PdfReadError

from web_mcp.logging import get_logger

__all__ = [
    "PDFExtractionError",
    "PaginatedPDF",
    "PDFCache",
    "extract_text_from_pdf",
    "pdf_to_markdown",
    "is_pdf_content_type",
    "paginate_markdown",
    "MAX_PDF_SIZE",
    "DEFAULT_CHARS_PER_PAGE",
]

logger = get_logger(__name__)

MAX_PDF_SIZE: Final[int] = 100 * 1024 * 1024  # 100MB
DEFAULT_CHARS_PER_PAGE: Final[int] = 120_000

# Pre-compiled regex to remove control characters (keep \n, \r, \t)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]+")


class PDFExtractionError(Exception):
    """Raised when PDF extraction fails."""

    pass


@dataclass(frozen=True, slots=True)
class PaginatedPDF:
    """Paginated PDF content."""

    content: str
    current_page: int
    total_pages: int


def _read_pdf_pages(pdf_bytes: bytes) -> list[str]:
    """Read all pages from a PDF and return extracted text.

    Args:
        pdf_bytes: PDF content as bytes

    Returns:
        List of extracted text from each page

    Raises:
        PDFExtractionError: If PDF reading fails
    """
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        pages: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                # Fast: just strip control characters
                pages.append(_CONTROL_CHARS.sub("", page_text))
        return pages
    except (PdfReadError, DependencyError) as e:
        logger.error("Failed to read PDF: %s", e)
        raise PDFExtractionError(f"Failed to read PDF: {e}") from e


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from a PDF file.

    Args:
        pdf_bytes: PDF content as bytes

    Returns:
        Extracted text from all pages

    Raises:
        PDFExtractionError: If extraction fails or PDF exceeds size limit
    """
    if len(pdf_bytes) > MAX_PDF_SIZE:
        logger.error("PDF exceeds size limit: %d bytes", len(pdf_bytes))
        raise PDFExtractionError(f"PDF exceeds maximum size limit of {MAX_PDF_SIZE} bytes")

    pages = _read_pdf_pages(pdf_bytes)
    return "\n\n".join(pages)


def pdf_to_markdown(pdf_bytes: bytes, url: str) -> str:
    """Convert PDF content to markdown format.

    Args:
        pdf_bytes: PDF content as bytes
        url: Source URL for the PDF (used in header)

    Returns:
        Markdown-formatted string with page headers

    Raises:
        PDFExtractionError: If conversion fails or PDF exceeds size limit
    """
    if len(pdf_bytes) > MAX_PDF_SIZE:
        logger.error("PDF exceeds size limit: %d bytes", len(pdf_bytes))
        raise PDFExtractionError(f"PDF exceeds maximum size limit of {MAX_PDF_SIZE} bytes")

    pages = _read_pdf_pages(pdf_bytes)
    markdown_parts = [f"# PDF: {url}\n"]

    for i, page_text in enumerate(pages, start=1):
        markdown_parts.append(f"\n## Page {i}\n\n{page_text}")

    return "\n".join(markdown_parts)


def is_pdf_content_type(content_type: str) -> bool:
    """Check if content-type indicates a PDF.

    Args:
        content_type: The content-type header value

    Returns:
        True if content-type indicates a PDF, False otherwise
    """
    if not content_type:
        return False
    normalized = content_type.lower().strip()
    return normalized.startswith("application/pdf")


def paginate_markdown(
    markdown_text: str, page: int = 0, chars_per_page: int = DEFAULT_CHARS_PER_PAGE
) -> PaginatedPDF:
    """Split markdown text into paginated chunks.

    Args:
        markdown_text: The markdown text to paginate
        page: The page number to return (0-indexed)
        chars_per_page: Target characters per page (default 120k = ~30k tokens)

    Returns:
        PaginatedPDF with content, current_page, and total_pages

    Raises:
        ValueError: If page is negative
    """
    if page < 0:
        raise ValueError(f"Page must be >= 0, got {page}")

    if not markdown_text:
        return PaginatedPDF(content="", current_page=0, total_pages=1)

    paragraphs = markdown_text.split("\n\n")
    pages: list[str] = []
    current_page_content: list[str] = []
    current_length = 0

    for para in paragraphs:
        if not para:
            continue

        para_len = len(para) + 2

        if current_length + para_len > chars_per_page and current_page_content:
            pages.append("\n\n".join(current_page_content))
            current_page_content = []
            current_length = 0

        current_page_content.append(para)
        current_length += para_len

    if current_page_content:
        pages.append("\n\n".join(current_page_content))

    if not pages:
        pages = [""]

    total_pages = len(pages)
    safe_page = min(page, total_pages - 1)

    return PaginatedPDF(content=pages[safe_page], current_page=safe_page, total_pages=total_pages)


class PDFCache:
    """Simple in-memory cache for processed PDF content with TTL and LRU eviction."""

    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 50):
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._ttl = ttl_seconds
        self._max_entries = max_entries

    def _make_key(self, url: str) -> str:
        sanitized = url.replace("\x00", "")
        return sha256(sanitized.encode()).hexdigest()

    def __len__(self) -> int:
        return len(self._cache)

    def get(self, url: str) -> str | None:
        """Get cached markdown for URL, returns None if not found or expired."""
        key = self._make_key(url)
        if key not in self._cache:
            return None
        markdown, timestamp = self._cache[key]
        if time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        self._cache.move_to_end(key)
        return markdown

    def set(self, url: str, markdown: str) -> None:
        """Cache markdown for URL."""
        key = self._make_key(url)
        if key in self._cache:
            del self._cache[key]
        elif len(self._cache) >= self._max_entries:
            self._cache.popitem(last=False)
        self._cache[key] = (markdown, time())

    def clear_expired(self) -> None:
        """Remove expired entries."""
        current_time = time()
        expired_keys = [
            key
            for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self._ttl
        ]
        for key in expired_keys:
            del self._cache[key]
