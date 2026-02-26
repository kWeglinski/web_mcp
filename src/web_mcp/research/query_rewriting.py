"""Query rewriting utilities for improved search results."""

import asyncio
from typing import List, Optional

from web_mcp.llm.client import LLMClient, LLMError
from web_mcp.llm.config import get_llm_config


SYSTEM_PROMPT = """You are a query optimization assistant. Given a user question, 
generate an optimized search query that will return the most relevant results.

Rules:
1. Keep the core intent
2. Add relevant keywords
3. Remove conversational filler
4. Return ONLY the optimized query, nothing else"""


async def rewrite_query(client: LLMClient, query: str) -> Optional[str]:
    """Rewrite a user query for better search results.
    
    Uses the LLM to expand and optimize the query while preserving intent.
    
    Args:
        client: LLM client for generation
        query: Original user query
        
    Returns:
        Rewritten query string, or None if rewriting fails
    """
    try:
        config = get_llm_config()
        
        # Check if LLM is configured
        if not config.is_configured:
            return None
        
        # Use a lower temperature for more deterministic output
        result = await client.chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            max_tokens=100,
            temperature=0.3,
        )
        
        # Clean up the result
        rewritten = result.strip()
        
        # Return None if the result is empty or just whitespace
        if not rewritten:
            return None
        
        return rewritten
        
    except LLMError:
        # If LLM fails, return original query
        return None
    except Exception:
        # Any other error, return original query
        return None


async def generate_sub_queries(client: LLMClient, query: str) -> List[str]:
    """Generate multiple search queries from a single question.
    
    Breaks down complex questions into 2-3 specific search queries
    that can be executed in parallel for better coverage.
    
    Args:
        client: LLM client for generation
        query: Original user query
        
    Returns:
        List of 2-3 specific search queries
    """
    try:
        config = get_llm_config()
        
        if not config.is_configured:
            return [query]
        
        prompt = f"""Break down this question into 2-3 specific search queries.
Each query should focus on a different aspect of the question.

Question: {query}

Return one query per line, numbered 1., 2., 3. etc."""
        
        result = await client.chat(
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.3,
        )
        
        # Parse the results
        queries = []
        for line in result.strip().split('\n'):
            # Remove leading numbers and bullet points
            query_text = line.strip()
            for prefix in ['1.', '2.', '3.', '4.', '5.', '- ', '* ', '• ']:
                if query_text.startswith(prefix):
                    query_text = query_text[len(prefix):].strip()
            if query_text:
                queries.append(query_text)
        
        # If parsing failed, return original
        if not queries:
            return [query]
        
        return queries
        
    except Exception:
        # If anything fails, return original query
        return [query]


def expand_query_with_keywords(query: str) -> str:
    """Simple keyword expansion without LLM.
    
    Adds common search optimization patterns to improve results.
    
    Args:
        query: Original query
        
    Returns:
        Expanded query string
    """
    # Common search optimization patterns
    patterns = [
        f"{query} site:wikipedia.org",
        f"define {query}",
        f"{query} tutorial",
        f"best {query} guide",
    ]
    
    # Return combined query
    return " OR ".join(patterns)


async def generate_query_variants(client: LLMClient, query: str) -> List[str]:
    """Generate multiple query variants for better search coverage.
    
    Uses the LLM to generate different perspectives on the same question,
    then combines them for a comprehensive search.
    
    Args:
        client: LLM client for generation
        query: Original user query
        
    Returns:
        List of query variants including original and rewritten versions
    """
    try:
        config = get_llm_config()
        
        if not config.is_configured:
            return [query]
        
        # Generate sub-queries
        sub_queries = await generate_sub_queries(client, query)
        
        # Combine with original and keyword-expanded versions
        variants = [query]
        
        # Add sub-queries if they're different
        for sq in sub_queries:
            if sq != query and sq not in variants:
                variants.append(sq)
        
        # Add keyword-expanded version
        expanded = expand_query_with_keywords(query)
        if expanded not in variants:
            variants.append(expanded)
        
        return variants
        
    except Exception:
        return [query]


async def parallel_search_queries(
    client: LLMClient,
    query: str,
    search_func,
    max_concurrent: int = 3
) -> List:
    """Execute multiple search queries in parallel.
    
    Takes a query, generates variants, and executes all searches
    concurrently for better coverage.
    
    Args:
        client: LLM client for generation
        query: Original user query
        search_func: Async function to execute search
        max_concurrent: Maximum concurrent searches
        
    Returns:
        Combined results from all searches
    """
    # Generate query variants
    variants = await generate_query_variants(client, query)
    
    # Limit concurrent searches
    variants = variants[:max_concurrent]
    
    # Execute all searches in parallel
    tasks = [search_func(variant) for variant in variants if variant]
    
    # Run with semaphore to limit concurrency
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def bounded_search(variant):
        async with semaphore:
            return await search_func(variant)
    
    tasks = [bounded_search(v) for v in variants if v]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Combine results
    combined_results = []
    for result in results:
        if isinstance(result, list):
            combined_results.extend(result)
        elif isinstance(result, dict):
            combined_results.append(result)
    
    return combined_results
