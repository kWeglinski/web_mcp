# Research Pipeline Guide

## Overview

The research pipeline is the most powerful feature of the Web Browsing MCP Server. It combines web search, content extraction, embeddings, and LLM generation to provide comprehensive answers with citations.

## Research Flow

```
Question
    ↓
1. Search (SearXNG)
    ↓
2. Fetch & Extract (Trafilatura/Readability)
3. Chunk Text
4. Generate Embeddings
5. Find Relevant Chunks
6. Rerank Results
7. Build Context with Citations
8. Generate Answer (LLM)
9. Validate Citations
    ↓
Answer with Sources
```

## The `ask` Tool

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `question` | string | - | The question to research (required) |
| `max_sources` | integer | 5 | Maximum number of sources to use |
| `search_results` | integer | 10 | Number of search results to fetch |

### Example

```python
from web_mcp.server import ask

result = await ask(
    question="What are the latest developments in quantum computing?",
    max_sources=5,
    search_results=10
)

print(f"Answer: {result.answer}")
for source in result.sources:
    print(f"[{source.index}] {source.title}")
```

### Response Format

```json
{
  "answer": "Quantum computing is a type of computation whose operations perform calculations using quantum mechanics. It uses quantum bits (qubits) which can exist in multiple states simultaneously...",
  "sources": [
    {
      "index": 1,
      "url": "https://example.com/quantum",
      "title": "Quantum Computing Basics",
      "snippet": "Quantum computing uses quantum mechanics..."
    },
    {
      "index": 2,
      "url": "https://example.com/quantum-advantage",
      "title": "Quantum Advantage 2024",
      "snippet": "Recent breakthroughs in quantum computing..."
    }
  ],
  "elapsed_ms": 15234
}
```

## The `ask_stream` Tool

Streaming version of `ask` that yields chunks as they're generated.

### Example

```python
from web_mcp.server import ask_stream

async def main():
    parts = []
    async for chunk in ask_stream(
        question="What are the latest developments in quantum computing?",
        max_sources=5,
        search_results=10
    ):
        parts.append(chunk)
    
    result = "".join(parts)
    print(result)
```

## Research Pipeline Components

### 1. Search ([`searxng.py`](../src/web_mcp/searxng.py))

Searches the web using SearXNG:

```python
from web_mcp.searxng import search

results = await search(
    query="quantum computing 2024",
    max_results=10
)
```

### 2. Fetch & Extract ([`fetcher.py`](../src/web_mcp/fetcher.py))

Fetches and extracts content from URLs:

```python
from web_mcp.fetcher import fetch_url
from web_mcp.extractors.trafilatura import TrafilaturaExtractor

html = await fetch_url(url, config)
extractor = TrafilaturaExtractor()
content = await extractor.extract(html, url)
```

### 3. Chunking ([`research/chunker.py`](../src/web_mcp/research/chunker.py))

Splits text into manageable chunks:

```python
from web_mcp.research.chunker import chunk_text

chunks = chunk_text(
    text=content.text,
    source_url=url,
    source_title=title,
    chunk_size=1000,
    overlap=200
)
```

### 4. Embeddings ([`llm/embeddings.py`](../src/web_mcp/llm/embeddings.py))

Generates embeddings for chunks and queries:

```python
from web_mcp.llm.embeddings import embed_chunks, embed_query

# Embed chunks
embedded = await embed_chunks(client, chunk_tuples)

# Embed query
query_embedding = await embed_query(client, query)
```

### 5. Relevance Finding ([`llm/embeddings.py`](../src/web_mcp/llm/embeddings.py))

Finds most relevant chunks:

```python
from web_mcp.llm.embeddings import find_most_relevant

relevant = find_most_relevant(
    query_embedding,
    embedded_chunks,
    top_k=15
)
```

### 6. Reranking ([`research/reranking.py`](../src/web_mcp/research/reranking.py))

Reranks chunks for better relevance:

```python
from web_mcp.research.reranking import rerank_chunks

relevant = await rerank_chunks(
    client, query, relevant, top_k=15
)
```

### 7. Citation Building ([`research/citations.py`](../src/web_mcp/research/citations.py))

Builds context with citation markers:

```python
from web_mcp.research.citations import build_context_with_citations

context, sources = build_context_with_citations(relevant)
```

### 8. Answer Generation ([`llm/client.py`](../src/web_mcp/llm/client.py))

Generates answer using LLM:

```python
from web_mcp.llm.client import get_llm_client

client = get_llm_client()
answer = await client.chat([
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_message}
])
```

## Citation System

### Citation Format

Citations use square brackets: `[1]`, `[2]`, etc.

### Example Output

```
Quantum computing is a type of computation whose operations perform calculations using quantum mechanics [1]. It uses quantum bits (qubits) which can exist in multiple states simultaneously [2]. This allows quantum computers to solve certain problems much faster than classical computers [3].
```

### Source List

```python
[
    {
        "index": 1,
        "url": "https://example.com/quantum",
        "title": "Quantum Computing Basics"
    },
    {
        "index": 2,
        "url": "https://example.com/qubits",
        "title": "Understanding Qubits"
    },
    {
        "index": 3,
        "url": "https://example.com/quantum-advantage",
        "title": "Quantum Advantage 2024"
    }
]
```

## Configuration

### Research Settings

```bash
# Chunk size for text chunking
WEB_MCP_CHUNK_SIZE=1000

# Overlap between chunks
WEB_MCP_CHUNK_OVERLAP=200

# Number of top chunks to consider
WEB_MCP_TOP_CHUNKS=15

# Enable reranking
WEB_MCP_RERANK_ENABLED=true
```

### LLM Settings

```bash
# API key (required)
WEB_MCP_LLM_API_KEY=sk-...

# API endpoint
WEB_MCP_LLM_API_URL=https://api.openai.com/v1

# Generation model
WEB_MCP_LLM_MODEL=gpt-4o

# Embedding model
WEB_MCP_LLM_EMBED_MODEL=text-embedding-3-small
```

## Customizing the Research Pipeline

### 1. Modify Chunking

```python
from web_mcp.research.chunker import chunk_text

# Custom chunk size and overlap
chunks = chunk_text(
    text=text,
    source_url=url,
    source_title=title,
    chunk_size=500,  # Smaller chunks
    overlap=100      # Less overlap
)
```

### 2. Modify Top Chunks

```python
# Use more chunks for research
relevant = find_most_relevant(
    query_embedding,
    embedded_chunks,
    top_k=25  # More chunks to consider
)
```

### 3. Modify Reranking

```python
# Adjust reranking parameters
relevant = await rerank_chunks(
    client, query, relevant, top_k=20
)
```

## Error Handling

### LLM Not Configured

```python
from web_mcp.llm.config import get_llm_config

llm_config = get_llm_config()
if not llm_config.is_configured:
    print("LLM is not configured. Set WEB_MCP_LLM_API_KEY.")
```

### Search Errors

```python
from web_mcp.searxng import SearXNGError

try:
    results = await search(query, max_results)
except SearXNGError as e:
    print(f"Search failed: {e}")
```

### Fetch Errors

```python
from web_mcp.fetcher import FetchError

try:
    html = await fetch_url(url, config)
except FetchError as e:
    print(f"Fetch failed: {e}")
```

## Best Practices

1. **Set appropriate max_sources** - More sources = more comprehensive answers
2. **Use ask_stream for long tasks** - See progress as it happens
3. **Handle citations properly** - Don't modify citation numbers
4. **Validate sources** - Check that sources are relevant to your use case
