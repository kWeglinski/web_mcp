"""Fetching tools: get_page and render_html."""

from web_mcp.config import get_config
from web_mcp.content_store import get_content_store
from web_mcp.fetcher import FetchedContent, FetchError, fetch_url_with_metadata
from web_mcp.logging import get_logger
from web_mcp.pdf_processor import (
    PDFCache,
    PDFExtractionError,
    is_pdf_content_type,
    paginate_markdown,
    pdf_to_markdown,
)
from web_mcp.playwright_fetcher import PlaywrightFetchError
from web_mcp.research.bm25 import BM25
from web_mcp.research.chunker import chunk_text
from web_mcp.security import validate_url, validate_url_ip
from web_mcp.tools._core import increment_request_count

logger = get_logger(__name__)

BM25_CHUNK_SIZE = 500
BM25_CHUNK_OVERLAP = 50
BM25_TOP_CHUNKS = 5
MAX_FALLBACK_TEXT_LENGTH = 10000
MAX_FALLBACK_HTML_LENGTH = 2000

HTML_WRAPPER_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="default-src 'unsafe-inline' 'unsafe-eval' data:; script-src 'none'; object-src 'none';">
</head>
<body>
{content}
</body>
</html>"""

_default_extractor = None
_custom_extractor = None
_pdf_cache = None


def _get_default_extractor():
    """Lazy-initialize the default extractor."""
    global _default_extractor
    if _default_extractor is None:
        from web_mcp.extractors.trafilatura import TrafilaturaExtractor
        _default_extractor = TrafilaturaExtractor()
    return _default_extractor


def _get_custom_extractor():
    """Lazy-initialize the custom extractor."""
    global _custom_extractor
    if _custom_extractor is None:
        from web_mcp.extractors.custom import CustomSelectorExtractor
        _custom_extractor = CustomSelectorExtractor()
    return _custom_extractor


def _get_pdf_cache():
    """Lazy-initialize the PDF cache."""
    global _pdf_cache
    if _pdf_cache is None:
        _pdf_cache = PDFCache(ttl_seconds=3600)
    return _pdf_cache


def _rank_chunks_with_bm25(text: str, url: str, title: str, query: str) -> str:
    """Rank text chunks using BM25 and return top chunks.

    Args:
        text: The text to chunk and rank
        url: Source URL for chunk metadata
        title: Title for chunk metadata
        query: The search query for BM25 ranking

    Returns:
        Top ranked chunks joined by separator, or fallback text if chunking fails
    """
    chunks = chunk_text(
        text,
        url,
        title,
        chunk_size=BM25_CHUNK_SIZE,
        overlap=BM25_CHUNK_OVERLAP,
    )

    if not chunks:
        fallback_len = min(len(text), MAX_FALLBACK_TEXT_LENGTH)
        return text[:fallback_len]

    documents = [{"text": c.text, "chunk": c} for c in chunks]
    bm25 = BM25()
    bm25.fit(documents, text_field="text")
    ranked = bm25.rank(query)

    top_chunks = ranked[:BM25_TOP_CHUNKS]

    parts = []
    for doc, _score in top_chunks:
        chunk = doc["chunk"]
        parts.append(chunk.text)

    return "\n\n---\n\n".join(parts)


async def get_page(
    url: str,
    query: str | None = None,
    extractor: str = "trafilatura",
    page: int = 0,
) -> str:
    """Fetch and extract main content from a URL (HTML or PDF). Use query for BM25-ranked chunk retrieval. For large PDFs, use page parameter to paginate through content."""
    if page < 0:
        return "Error: page parameter must be non-negative"

    config = get_config()

    try:
        fetched = await fetch_url_with_metadata(url, config)
    except FetchError as e:
        if config.playwright_enabled:
            logger.info(f"tls-client fetch failed ({e}), trying Playwright fallback for: {url}")
            try:
                from web_mcp.playwright_fetcher import fetch_with_playwright_cached as pw_cached

                html = await pw_cached(url, config)
                fetched = FetchedContent(
                    content=html.encode("utf-8"), content_type="text/html", url=url
                )
            except PlaywrightFetchError as pe:
                return f"Error fetching URL (tls-client and Playwright both failed): {pe}"
        else:
            return f"Error fetching URL: {e}"

    if is_pdf_content_type(fetched.content_type):
        markdown_text = _get_pdf_cache().get(url)
        if markdown_text is None:
            try:
                markdown_text = pdf_to_markdown(fetched.content, url)
            except PDFExtractionError as e:
                return f"Error processing PDF: {e}"

            _get_pdf_cache().set(url, markdown_text)

        if query:
            return _rank_chunks_with_bm25(markdown_text, url, "PDF Document", query)

        paginated = paginate_markdown(markdown_text, page=page)
        current = paginated.current_page
        total = paginated.total_pages
        content = paginated.content

        if total == 1:
            return content

        next_page = current + 1

        if current == 0:
            header = f"[📄 CHUNK {current}/{total} - This PDF is split into {total} chunks due to size.]\n[To get more content, call: get_page(url, page=1), get_page(url, page=2), etc.]\n\n"
            footer = (
                f"\n\n---\nEnd of chunk {current}/{total}. Use page={next_page} for more content."
            )
        elif current == total - 1:
            header = f"[📄 CHUNK {current}/{total} - Final chunk]\n\n"
            footer = f"\n\n---\nEnd of chunk {current}/{total} (final)."
        else:
            header = f"[📄 CHUNK {current}/{total}]\n\n"
            footer = (
                f"\n\n---\nEnd of chunk {current}/{total}. Use page={next_page} for more content."
            )

        return f"{header}{content}{footer}"

    html = fetched.content.decode("utf-8", errors="replace")

    if query:
        try:
            extracted = await _get_default_extractor().extract(html, url)
        except Exception as e:
            return f"Error extracting content: {e}"

        if not extracted.text or not extracted.text.strip():
            return "No content extracted from page"

        ranked_result = _rank_chunks_with_bm25(extracted.text, url, extracted.title or url, query)

        header = f"Title: {extracted.title}\n\n" if extracted.title else ""
        return header + ranked_result

    if extractor == "readability":
        from web_mcp.extractors.readability import ReadabilityExtractor

        extractor_obj = ReadabilityExtractor()
    elif extractor == "custom":
        extractor_obj = _get_custom_extractor()
    else:
        extractor_obj = _get_default_extractor()

    try:
        extracted = await extractor_obj.extract(html, url)
    except Exception as e:
        return f"Error extracting content: {e}"

    return extracted.text


async def render_html(
    content: str,
) -> str:
    """Store HTML body content and return a viewable URL. Only provide the body/inner HTML - it will be wrapped in a basic HTML5 document with proper viewport meta tags. Requires WEB_MCP_PUBLIC_URL. Content expires after 1 hour."""
    increment_request_count()

    config = get_config()

    if not config.public_url:
        return "Error: WEB_MCP_PUBLIC_URL not configured. Set it to your server's public URL (e.g., https://mcp.example.com)"

    html = HTML_WRAPPER_TEMPLATE.format(content=content)

    store = get_content_store()
    content_id, token = store.store(html, content_type="text/html")

    url = f"{config.public_url}/c/{content_id}?token={token}"

    return url
