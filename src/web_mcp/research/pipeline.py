"""Research pipeline for web-grounded Q&A."""

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

from web_mcp.config import get_config
from web_mcp.extractors.trafilatura import TrafilaturaExtractor
from web_mcp.fetcher import FetchError
from web_mcp.fetcher import fetch_url_with_fallback as fetch_url
from web_mcp.llm.client import LLMError, get_llm_client
from web_mcp.llm.config import get_llm_config, get_research_config
from web_mcp.llm.embeddings import embed_chunks, embed_query, find_most_relevant
from web_mcp.research.chunker import chunk_text, merge_small_chunks
from web_mcp.research.citations import (
    Source,
    build_context_with_citations,
    format_sources,
    validate_citations,
)
from web_mcp.research.reranking import rerank_chunks, select_diverse_chunks
from web_mcp.searxng import SearXNGError, search


@dataclass
class ResearchResult:
    """Result of a research query."""

    answer: str
    sources: list[Source]
    elapsed_ms: int
    query: str


@dataclass
class FetchedContent:
    """Content fetched from a URL."""

    url: str
    title: str | None
    text: str
    error: str | None = None


_extractor = TrafilaturaExtractor()


async def _fetch_and_extract(url: str, title: str) -> FetchedContent:
    """Fetch and extract content from a URL."""
    config = get_config()

    try:
        html = await fetch_url(url, config)
        extracted = await _extractor.extract(html, url)
        return FetchedContent(
            url=url,
            title=title or extracted.title or url,
            text=extracted.text,
        )
    except FetchError as e:
        return FetchedContent(
            url=url,
            title=title or url,
            text="",
            error=str(e),
        )
    except Exception as e:
        return FetchedContent(
            url=url,
            title=title or url,
            text="",
            error=str(e),
        )


async def research(
    query: str,
    max_sources: int = 5,
    search_results: int = 10,
) -> ResearchResult:
    """Perform research on a query and return an answer with sources.

    Args:
        query: The question to research
        max_sources: Maximum number of sources to use
        search_results: Number of search results to fetch

    Returns:
        ResearchResult with answer, sources, and timing info
    """
    start_time = time.time()
    llm_config = get_llm_config()
    research_config = get_research_config()

    if not llm_config.is_configured:
        return ResearchResult(
            answer="Error: LLM not configured. Set WEB_MCP_LLM_API_KEY environment variable.",
            sources=[],
            elapsed_ms=int((time.time() - start_time) * 1000),
            query=query,
        )

    try:
        search_results_data = await search(query, search_results)
    except SearXNGError as e:
        return ResearchResult(
            answer=f"Error: Search failed - {e}",
            sources=[],
            elapsed_ms=int((time.time() - start_time) * 1000),
            query=query,
        )

    if not search_results_data:
        return ResearchResult(
            answer="No search results found for your query.",
            sources=[],
            elapsed_ms=int((time.time() - start_time) * 1000),
            query=query,
        )

    urls_to_fetch = [
        (r.get("url", ""), r.get("title", ""))
        for r in search_results_data[:search_results]
        if r.get("url")
    ]

    fetch_tasks = [_fetch_and_extract(url, title) for url, title in urls_to_fetch]
    fetched_contents = await asyncio.gather(*fetch_tasks)

    valid_contents = [c for c in fetched_contents if c.text and not c.error]

    if not valid_contents:
        return ResearchResult(
            answer="Could not fetch content from any of the search results.",
            sources=[],
            elapsed_ms=int((time.time() - start_time) * 1000),
            query=query,
        )

    all_chunks = []
    for content in valid_contents:
        chunks = chunk_text(
            content.text,
            content.url,
            content.title or content.url,
            chunk_size=research_config.chunk_size,
            overlap=research_config.chunk_overlap,
        )
        all_chunks.extend(chunks)

    all_chunks = merge_small_chunks(all_chunks)

    if not all_chunks:
        return ResearchResult(
            answer="Could not extract meaningful content from the search results.",
            sources=[],
            elapsed_ms=int((time.time() - start_time) * 1000),
            query=query,
        )

    client = get_llm_client()

    chunk_tuples = [(c.text, c.source_url, c.source_title, c.index) for c in all_chunks]

    try:
        # Run embedding and query embedding in parallel for speed
        embedded_chunks, query_embedding = await asyncio.gather(
            embed_chunks(client, chunk_tuples), embed_query(client, query)
        )
    except LLMError as e:
        return ResearchResult(
            answer=f"Error: Embedding failed - {e}",
            sources=[],
            elapsed_ms=int((time.time() - start_time) * 1000),
            query=query,
        )

    # Find most relevant chunks
    relevant = find_most_relevant(
        query_embedding,
        embedded_chunks,
        top_k=min(max_sources * 3, research_config.top_chunks),
    )

    # Apply reranking if enabled
    import os

    rerank_enabled = os.environ.get("WEB_MCP_RERANK_ENABLED", "true").lower() == "true"
    if rerank_enabled:
        try:
            relevant = await rerank_chunks(
                client, query, relevant, top_k=min(max_sources * 3, research_config.top_chunks)
            )
        except Exception:
            # If reranking fails, fall back to original results
            pass

    # Select diverse chunks to avoid too many from same source
    relevant = select_diverse_chunks(
        relevant,
        max_per_source=3,
        total_chunks=min(max_sources * 3, research_config.top_chunks),
    )

    context, sources = build_context_with_citations(relevant)

    system_prompt = """You are a research assistant that answers questions based on provided sources.

Rules:
1. Answer the question using ONLY the provided context
2. Use citation markers [1], [2], etc. to indicate which source each piece of information comes from
3. Be comprehensive but concise
4. If the context doesn't contain enough information, say so
5. Synthesize information from multiple sources when appropriate
6. Include relevant details and specifics from the sources"""

    user_message = f"""Context:
{context}

Question: {query}

Please answer the question using the provided context. Include citation markers [1], [2], etc. to indicate your sources."""

    try:
        answer = await client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
        )
    except LLMError as e:
        return ResearchResult(
            answer=f"Error: Generation failed - {e}",
            sources=[],
            elapsed_ms=int((time.time() - start_time) * 1000),
            query=query,
        )

    # Validate and fix citations
    validated_answer = validate_citations(answer, sources)
    if not validated_answer["valid"]:
        # Replace invalid citations with placeholder
        import re

        for idx in validated_answer.get("invalid_indices", []):
            answer = re.sub(rf"\[{idx}\]", "[?]", answer)

    elapsed_ms = int((time.time() - start_time) * 1000)

    return ResearchResult(
        answer=answer,
        sources=sources,
        elapsed_ms=elapsed_ms,
        query=query,
    )


async def research_stream(
    query: str,
    max_sources: int = 5,
    search_results: int = 10,
) -> AsyncIterator[str]:
    """Stream a research answer.

    This yields the answer in chunks, then yields the sources at the end.

    Args:
        query: The question to research
        max_sources: Maximum number of sources to use
        search_results: Number of search results to fetch

    Yields:
        Chunks of the answer, followed by formatted sources
    """
    llm_config = get_llm_config()
    research_config = get_research_config()

    if not llm_config.is_configured:
        yield "Error: LLM not configured. Set WEB_MCP_LLM_API_KEY environment variable."
        return

    try:
        search_results_data = await search(query, search_results)
    except SearXNGError as e:
        yield f"Error: Search failed - {e}"
        return

    if not search_results_data:
        yield "No search results found for your query."
        return

    urls_to_fetch = [
        (r.get("url", ""), r.get("title", ""))
        for r in search_results_data[:search_results]
        if r.get("url")
    ]

    fetch_tasks = [_fetch_and_extract(url, title) for url, title in urls_to_fetch]
    fetched_contents = await asyncio.gather(*fetch_tasks)

    valid_contents = [c for c in fetched_contents if c.text and not c.error]

    if not valid_contents:
        yield "Could not fetch content from any of the search results."
        return

    all_chunks = []
    for content in valid_contents:
        chunks = chunk_text(
            content.text,
            content.url,
            content.title or content.url,
            chunk_size=research_config.chunk_size,
            overlap=research_config.chunk_overlap,
        )
        all_chunks.extend(chunks)

    all_chunks = merge_small_chunks(all_chunks)

    if not all_chunks:
        yield "Could not extract meaningful content from the search results."
        return

    client = get_llm_client()

    chunk_tuples = [(c.text, c.source_url, c.source_title, c.index) for c in all_chunks]

    try:
        embedded_chunks = await embed_chunks(client, chunk_tuples)
        query_embedding = await embed_query(client, query)
    except LLMError as e:
        yield f"Error: Embedding failed - {e}"
        return

    relevant = find_most_relevant(
        query_embedding,
        embedded_chunks,
        top_k=min(max_sources * 3, research_config.top_chunks),
    )

    context, sources = build_context_with_citations(relevant)

    system_prompt = """You are a research assistant that answers questions based on provided sources.

Rules:
1. Answer the question using ONLY the provided context
2. Use citation markers [1], [2], etc. to indicate which source each piece of information comes from
3. Be comprehensive but concise
4. If the context doesn't contain enough information, say so
5. Synthesize information from multiple sources when appropriate
6. Include relevant details and specifics from the sources"""

    user_message = f"""Context:
{context}

Question: {query}

Please answer the question using the provided context. Include citation markers [1], [2], etc. to indicate your sources."""

    try:
        async for chunk in client.chat_stream(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]
        ):
            yield chunk
    except LLMError as e:
        yield f"\n\nError: Generation failed - {e}"
        return

    if sources:
        yield "\n\n---\n\n**Sources:**\n\n"
        yield format_sources(sources)
