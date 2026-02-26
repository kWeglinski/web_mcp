"""Embedding utilities with similarity search."""

import asyncio
import math
from dataclasses import dataclass
from typing import List, Tuple

from web_mcp.llm.client import LLMClient, LLMError
from web_mcp.llm.embedding_cache import get_embedding_cache


@dataclass
class EmbeddedChunk:
    """A chunk of text with its embedding and source info."""
    text: str
    embedding: List[float]
    source_url: str
    source_title: str
    chunk_index: int


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(a) != len(b):
        raise ValueError("Vectors must have the same length")
    
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


async def _embed_batch(client: LLMClient, texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts with retry logic.
    
    Args:
        client: LLM client for embeddings
        texts: List of text strings to embed
        
    Returns:
        List of embedding vectors
    """
    max_retries = 3
    base_delay = 1.0
    
    for attempt in range(max_retries):
        try:
            return await client.embed(texts)
        except LLMError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
            else:
                raise


async def embed_chunks(
    client: LLMClient,
    chunks: List[Tuple[str, str, str, int]],
    batch_size: int = 50,
) -> List[EmbeddedChunk]:
    """Embed a list of chunks with caching and batch processing.
    
    Uses the embedding cache to avoid re-embedding identical content,
    processes remaining chunks in parallel batches, and includes
    retry logic for robustness.
    
    Args:
        client: LLM client for embeddings
        chunks: List of (text, source_url, source_title, chunk_index)
        batch_size: Number of chunks per API call
        
    Returns:
        List of EmbeddedChunk objects
    """
    if not chunks:
        return []
    
    cache = get_embedding_cache()
    
    # Separate cached and uncached chunks
    cached_results = []
    uncached_chunks = []
    
    for chunk in chunks:
        text = chunk[0]
        cached_embedding = cache.get(text)
        
        if cached_embedding is not None:
            cached_results.append(EmbeddedChunk(
                text=text,
                embedding=cached_embedding,
                source_url=chunk[1],
                source_title=chunk[2],
                chunk_index=chunk[3],
            ))
        else:
            uncached_chunks.append(chunk)
    
    # Process uncached chunks in parallel batches
    all_uncached_embeddings = []
    
    if uncached_chunks:
        # Group chunks into batches
        batches = []
        for i in range(0, len(uncached_chunks), batch_size):
            batch = uncached_chunks[i:i + batch_size]
            batches.append((batch, [c[0] for c in batch]))
        
        # Process all batches in parallel
        async def process_batch(batch, texts):
            try:
                embeddings = await _embed_batch(client, texts)
                # Cache the embeddings
                for chunk, emb in zip(batch, embeddings):
                    cache.set(chunk[0], emb)
                return list(zip(batch, embeddings))
            except LLMError:
                # If batch fails, try individual chunks
                results = []
                for chunk in batch:
                    try:
                        embeddings = await _embed_batch(client, [chunk[0]])
                        cache.set(chunk[0], embeddings[0])
                        results.append((chunk, embeddings[0]))
                    except LLMError:
                        pass
                return results
        
        # Run all batch tasks in parallel
        batch_tasks = [process_batch(batch, texts) for batch, texts in batches]
        batch_results = await asyncio.gather(*batch_tasks)
        
        # Flatten results
        for result in batch_results:
            all_uncached_embeddings.extend([emb for _, emb in result])
    
    # Combine cached and newly embedded results
    all_embeddings = []
    uncached_idx = 0
    
    for chunk in chunks:
        text = chunk[0]
        cached_embedding = cache.get(text)
        
        if cached_embedding is not None:
            all_embeddings.append(cached_embedding)
        else:
            if uncached_idx < len(all_uncached_embeddings):
                all_embeddings.append(all_uncached_embeddings[uncached_idx])
                uncached_idx += 1
            else:
                # Fallback: create zero embedding
                all_embeddings.append([0.0] * 384)
    
    return [
        EmbeddedChunk(
            text=chunk[0],
            embedding=emb,
            source_url=chunk[1],
            source_title=chunk[2],
            chunk_index=chunk[3],
        )
        for chunk, emb in zip(chunks, all_embeddings)
    ]


async def embed_query(client: LLMClient, query: str) -> List[float]:
    """Embed a single query with caching.
    
    Args:
        client: LLM client for embeddings
        query: Query string to embed
        
    Returns:
        Embedding vector
    """
    cache = get_embedding_cache()
    
    # Check cache first
    cached = cache.get(query)
    if cached is not None:
        return cached
    
    # Embed and cache
    try:
        embeddings = await _embed_batch(client, [query])
        embedding = embeddings[0]
    except LLMError:
        # Fallback: create zero embedding
        return [0.0] * 384
    
    # Cache for future use
    cache.set(query, embedding)
    
    return embedding


def find_most_relevant(
    query_embedding: List[float],
    chunks: List[EmbeddedChunk],
    top_k: int = 10,
) -> List[Tuple[EmbeddedChunk, float]]:
    """Find the most relevant chunks for a query.
    
    Args:
        query_embedding: Embedding of the query
        chunks: List of embedded chunks
        top_k: Number of top results to return
    
    Returns:
        List of (chunk, similarity_score) tuples, sorted by relevance
    """
    scored = [
        (chunk, cosine_similarity(query_embedding, chunk.embedding))
        for chunk in chunks
    ]
    
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
