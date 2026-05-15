"""Specialized research pipeline for the Kiwix (Wikipedia) server."""

import asyncio
import logging
import time
from dataclasses import dataclass

from web_mcp.kiwix_client import KiwixClient
from web_mcp.kiwix_processor import ContentCleaner, SemanticChunker
from web_mcp.llm.client import LLMError, get_llm_client
from web_mcp.llm.config import get_llm_config, get_research_config
from web_mcp.llm.embeddings import embed_chunks, embed_query, find_most_relevant
from web_mcp.research.citations import Source, build_context_with_citations
from web_mcp.research.query_rewriting import generate_sub_queries, rewrite_query
from web_mcp.research.reranking import rerank_chunks, select_diverse_chunks_v2

logger = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    """Result of a Kiwix research query."""

    answer: str
    sources: list[Source]
    elapsed_ms: int
    query: str


@dataclass
class KiwixChunk:
    """A chunk of content from Kiwix."""

    text: str
    url: str  # This will be the path in Kiwix
    title: str
    index: int


async def research_kiwix(
    query: str,
    max_sources: int = 5,
    search_results_limit: int = 10,
) -> ResearchResult:
    """Perform research on a Kiwix server and return an answer with sources.

    Args:
        query: The question to research
        max_sources: Maximum number of sources to use
        search_results_limit: Number of search results to fetch

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

    client = get_llm_client()
    kiwix_client = KiwixClient()
    cleaner = ContentCleaner()
    chunker = SemanticChunker()

    effective_query = query
    sub_queries = [query]

    # Step 1: Query Expansion
    if research_config.rewrite_enabled and llm_config.is_configured:
        try:
            rewritten = await rewrite_query(client, query)
            if rewritten and rewritten != query:
                effective_query = rewritten
        except Exception as e:
            logger.warning(f"Query rewriting failed: {e}")

        try:
            sub_queries = await generate_sub_queries(client, query)
            if not sub_queries:
                sub_queries = [query]
        except Exception as e:
            logger.warning(f"Sub-query generation failed: {e}")

    # Step 2: Kiwix Search
    all_search_results = []
    try:
        if len(sub_queries) > 1 and research_config.rewrite_enabled:
            semaphore = asyncio.Semaphore(3)

            async def bounded_search(q: str):
                async with semaphore:
                    return await kiwix_client.search(q)

            tasks = [bounded_search(sq) for sq in sub_queries]
            search_responses = await asyncio.gather(*tasks, return_exceptions=True)

            for resp in search_responses:
                if isinstance(resp, list):
                    all_search_results.extend(resp)
                elif isinstance(resp, Exception):
                    logger.warning(f"Sub-query search failed: {resp}")
        else:
            all_search_results = await kiwix_client.search(effective_query)
    except Exception as e:
        logger.error(f"Kiwix search failed: {e}")
        return ResearchResult(
            answer=f"Error during Kiwix search: {e}",
            sources=[],
            elapsed_ms=int((time.time() - start_time) * 1000),
            query=query,
        )

    if not all_search_results:
        return ResearchResult(
            answer="No search results found in Kiwix.",
            sources=[],
            elapsed_ms=int((time.time() - start_time) * 1000),
            query=query,
        )

    # Limit search results to what we requested
    search_results = all_search_results[:search_results_limit]

    # Step 3: Content Retrieval & Processing
    all_chunks = []

    async def fetch_and_process(result: dict, idx: int):
        path = result.get("path") or result.get("url")
        title = result.get("title") or "Unknown Title"

        if not path:
            return []

        try:
            html_content = await kiwix_client.get_content(path)
            cleaned_text = cleaner.clean(html_content)
            # SemanticChunker returns List[str]
            chunks = chunker.chunk(cleaned_text)

            processed_chunks = []
            for i, chunk_text in enumerate(chunks):
                processed_chunks.append(
                    KiwixChunk(
                        text=chunk_text,
                        url=path,
                        title=title,
                        index=idx * 1000 + i,  # Ensure unique index for citations
                    )
                )
            return processed_chunks
        except Exception as e:
            logger.warning(f"Failed to fetch/process content from {path}: {e}")
            return []

    fetch_tasks = [fetch_and_process(res, i) for i, res in enumerate(search_results)]
    results = await asyncio.gather(*fetch_tasks)

    for chunk_list in results:
        all_chunks.extend(chunk_list)

    if not all_chunks:
        return ResearchResult(
            answer="Could not retrieve or process any meaningful content from Kiwix results.",
            sources=[],
            elapsed_ms=int((time.time() - start_time) * 1000),
            query=query,
        )

    # Step 4: RAG Pipeline
    chunk_tuples = [(c.text, c.url, c.title, c.index) for c in all_chunks]

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

    # (Optional) Apply reranking and diversity selection if configured
    import os

    rerank_enabled = os.environ.get("WEB_MCP_RERANK_ENABLED", "true").lower() == "true"
    if rerank_enabled:
        try:
            relevant = await rerank_chunks(
                client, query, relevant, top_k=min(max_sources * 3, research_config.top_chunks)
            )
        except Exception:
            pass

    relevant = select_diverse_chunks_v2(
        relevant,
        max_per_source=3,
        total_chunks=min(max_sources * 3, research_config.top_chunks),
    )

    # Step 5: Generation
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

    # Step 6: Cleanup
    elapsed_ms = int((time.time() - start_time) * 1000)

    return ResearchResult(
        answer=answer,
        sources=sources,
        elapsed_ms=elapsed_ms,
        query=query,
    )
