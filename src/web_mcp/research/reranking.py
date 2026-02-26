"""Result reranking utilities for improved relevance."""

import asyncio
import re
from typing import List, Tuple

from web_mcp.llm.client import LLMClient, LLMError
from web_mcp.llm.embeddings import EmbeddedChunk

_MAX_CONCURRENT_LLM_CALLS = 5


async def rerank_chunks(
    client: LLMClient,
    query: str,
    chunks: List[Tuple[EmbeddedChunk, float]],
    top_k: int = 10,
) -> List[Tuple[EmbeddedChunk, float]]:
    """Rerank chunks using LLM-based relevance scoring.
    
    Takes the top N chunks from semantic search and uses an LLM
    to score their relevance to the query, then returns the most
    relevant ones.
    
    Args:
        client: LLM client for scoring
        query: Original search query
        chunks: List of (chunk, semantic_score) tuples from find_most_relevant
        top_k: Number of chunks to return
        
    Returns:
        Reranked list of (chunk, relevance_score) tuples
    """
    if not chunks:
        return []
    
    candidates = chunks[:top_k * 2]
    
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_LLM_CALLS)
    
    async def score_chunk(chunk, semantic_score):
        async with semaphore:
            relevance_score = await score_relevance(client, query, chunk.text)
        return (chunk, relevance_score)
    
    tasks = [score_chunk(chunk, score) for chunk, score in candidates]
    scored_chunks = await asyncio.gather(*tasks)
    
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    
    return scored_chunks[:top_k]


async def score_relevance(
    client: LLMClient,
    query: str,
    text: str,
) -> float:
    """Score how relevant a text snippet is to a query.
    
    Uses the LLM to rate relevance on a 0-10 scale.
    
    Args:
        client: LLM client for generation
        query: Search query
        text: Text snippet to score
        
    Returns:
        Relevance score from 0.0 to 10.0
    """
    prompt = f"""Rate the relevance of this text to the query on a scale of 0-10.
    
Query: {query}
Text: {text[:500]}

Return ONLY a number from 0 to 10."""
    
    try:
        result = await client.chat(
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,
            temperature=0.1,
        )
        
        # Extract the number from the response
        score_match = re.search(r'(\d+\.?\d*)', result.strip())
        if score_match:
            score = float(score_match.group(1))
            return min(max(score, 0.0), 10.0)
        
        # Default score if parsing fails
        return 5.0
        
    except LLMError:
        # If LLM fails, return neutral score
        return 5.0
    except Exception:
        # Any other error, return neutral score
        return 5.0


def diversity_score(chunk: EmbeddedChunk, selected_urls: dict) -> float:
    """Calculate a diversity bonus for chunk selection.
    
    Penalizes chunks from URLs that are already represented in the
    selected results to promote source diversity.
    
    Args:
        chunk: The chunk to score
        selected_urls: Dict mapping URLs to their count in selected results
        
    Returns:
        Diversity bonus (0.0 to 1.0)
    """
    url = chunk.source_url
    count = selected_urls.get(url, 0)
    
    # Penalize heavily after 3 chunks from same source
    if count >= 3:
        return 0.0
    elif count >= 2:
        return 0.3
    elif count >= 1:
        return 0.5
    else:
        return 1.0


def select_diverse_chunks(
    chunks: List[Tuple[EmbeddedChunk, float]],
    max_per_source: int = 3,
    total_chunks: int = 15,
) -> List[Tuple[EmbeddedChunk, float]]:
    """Select chunks while promoting source diversity.
    
    Limits the number of chunks from any single URL to ensure
    broader coverage across sources. Uses a scoring system that
    balances relevance with diversity.
    
    Args:
        chunks: List of (chunk, score) tuples, sorted by score
        max_per_source: Maximum chunks allowed from same URL
        total_chunks: Total number of chunks to return
        
    Returns:
        Diversified list of (chunk, score) tuples
    """
    source_counts = {}
    selected = []
    
    for chunk, score in chunks:
        url = chunk.source_url
        
        # Track count per source
        if url not in source_counts:
            source_counts[url] = 0
        
        # Check if we can add this chunk
        if source_counts[url] < max_per_source:
            selected.append((chunk, score))
            source_counts[url] += 1
        
        # Check if we have enough
        if len(selected) >= total_chunks:
            break
    
    return selected


def select_diverse_chunks_v2(
    chunks: List[Tuple[EmbeddedChunk, float]],
    max_per_source: int = 3,
    total_chunks: int = 15,
) -> List[Tuple[EmbeddedChunk, float]]:
    """Select chunks while promoting source diversity with improved scoring.
    
    This version uses a more sophisticated approach that considers both
    relevance score and source diversity, using a scoring system that
    penalizes sources that are already well-represented.
    
    Args:
        chunks: List of (chunk, score) tuples, sorted by score
        max_per_source: Maximum chunks allowed from same URL
        total_chunks: Total number of chunks to return
        
    Returns:
        Diversified list of (chunk, combined_score) tuples
    """
    if not chunks:
        return []
    
    source_counts = {}
    selected = []
    
    for chunk, score in chunks:
        url = chunk.source_url
        
        # Track count per source
        if url not in source_counts:
            source_counts[url] = 0
        
        # Calculate diversity penalty
        count = source_counts[url]
        if count >= max_per_source:
            # Skip if we've reached the limit for this source
            continue
        
        # Diversity bonus: reduce penalty as count increases
        diversity_bonus = 1.0 - (count / (max_per_source + 1))
        
        # Combined score: original score * diversity bonus
        combined_score = score * diversity_bonus
        
        selected.append((chunk, combined_score))
        source_counts[url] += 1
        
        # Check if we have enough
        if len(selected) >= total_chunks:
            break
    
    # Sort by combined score and return
    selected.sort(key=lambda x: x[1], reverse=True)
    return selected


def select_diverse_chunks_rerank(
    chunks: List[Tuple[EmbeddedChunk, float]],
    max_per_source: int = 3,
    total_chunks: int = 15,
) -> List[Tuple[EmbeddedChunk, float]]:
    """Select diverse chunks with reranking based on combined scores.
    
    This version first applies diversity scoring to all candidates,
    then reranks them based on the combined score.
    
    Args:
        chunks: List of (chunk, score) tuples, sorted by score
        max_per_source: Maximum chunks allowed from same URL
        total_chunks: Total number of chunks to return
        
    Returns:
        Diversified and reranked list of (chunk, combined_score) tuples
    """
    if not chunks:
        return []
    
    source_counts = {}
    scored_chunks = []
    
    for chunk, score in chunks:
        url = chunk.source_url
        
        # Track count per source
        if url not in source_counts:
            source_counts[url] = 0
        
        count = source_counts[url]
        
        # Calculate diversity penalty
        if count >= max_per_source:
            continue
        
        diversity_bonus = 1.0 - (count / (max_per_source + 1))
        combined_score = score * diversity_bonus
        
        scored_chunks.append((chunk, combined_score))
        source_counts[url] += 1
    
    # Sort by combined score
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    
    return scored_chunks[:total_chunks]
