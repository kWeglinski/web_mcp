# Architecture Guide

## Overview

The Web Browsing MCP Server follows a modular, layered architecture designed for extensibility and maintainability.

## Core Components

### 1. Server Layer ([`server.py`](../src/web_mcp/server.py))

The server layer handles MCP protocol communication and exposes tools:

```python
mcp = FastMCP(
    name="web-browsing",
    instructions="A web browsing MCP server...",
    host=SERVER_HOST,
    port=SERVER_PORT,
)
```

**Tools:**
- `health()` - Server health metrics
- `fetch_url()` - Full content extraction with metadata
- `fetch_url_simple()` - Simplified text-only extraction
- `web_search()` - SearXNG search integration
- `ask()` - AI-powered research with citations
- `ask_stream()` - Streaming research results

### 2. Configuration Layer ([`config.py`](../src/web_mcp/config.py))

Configuration management using environment variables:

```python
class Config:
    max_tokens: int
    request_timeout: int
    default_extractor: str
    include_metadata: bool
    searxng_url: Optional[str]
```

**Features:**
- Environment-based configuration
- Validation with min/max bounds
- Global singleton pattern via `get_config()`

### 3. Fetching Layer ([`fetcher.py`](../src/web_mcp/fetcher.py))

HTTP fetching with connection pooling and caching:

```python
async def fetch_url(url: str, config, timeout: Optional[int] = None) -> str:
    # Uses httpx.AsyncClient with connection pooling
```

**Features:**
- Connection pool management (`get_connection_pool()`)
- Request timeout handling
- Error handling with custom `FetchError`
- LRU caching via `fetch_url_cached()`

### 4. Extraction Layer ([`extractors/`](../src/web_mcp/extractors/))

Content extraction with multiple strategies:

```python
class ContentExtractor(ABC):
    @abstractmethod
    async def extract(html: str, url: str) -> ExtractedContent:
        pass
```

**Extractors:**
- [`TrafilaturaExtractor`](extractors/trafilatura.py) - High-quality extraction
- [`ReadabilityExtractor`](extractors/readability.py) - Article-focused extraction
- [`CustomSelectorExtractor`](extractors/custom.py) - Custom CSS selector extraction

### 5. Optimization Layer ([`optimizer.py`](../src/web_mcp/optimizer.py))

Token estimation and content truncation:

```python
def estimate_tokens(text: str) -> int:
    # Rough estimation: 1 token ≈ 4 characters

def optimize_content(text: str, max_tokens: int, config) -> dict:
    # Truncates content to fit token limit
```

**Strategies:**
- `simple` - Character-based truncation
- `smart` - Paragraph-aware truncation

### 6. Search Layer ([`searxng.py`](../src/web_mcp/searxng.py))

SearXNG integration for web search:

```python
async def search(query: str, max_results: int = 10) -> list[dict]:
    # Returns list of search results
```

### 7. LLM Layer ([`llm/`](../src/web_mcp/llm/))

OpenAI-compatible API client:

```python
class LLMClient:
    async def embed(texts: List[str]) -> List[List[float]]:
        # Generate embeddings
        
    async def chat(messages: List[dict]) -> str:
        # Chat completion
        
    async def chat_stream(messages: List[dict]) -> AsyncIterator[str]:
        # Stream chat completion
```

### 8. Research Layer ([`research/`](../src/web_mcp/research/))

AI-powered research pipeline:

```python
async def research(query: str, max_sources: int = 5) -> ResearchResult:
    # 1. Search web for results
    # 2. Fetch and extract content
    # 3. Generate embeddings
    # 4. Find relevant chunks
    # 5. Generate answer with citations
```

## Data Flow

### Fetching Flow
```
User Request → fetch_url() → httpx.AsyncClient → HTML Content
```

### Extraction Flow
```
HTML Content → Extractor.extract() → ExtractedContent (title, author, text)
```

### Optimization Flow
```
Text Content → estimate_tokens() → Truncation → Optimized Text
```

### Research Flow
```
Question → Search → Fetch → Chunk → Embed → Rerank → Generate Answer
```

## Module Dependencies

```
server.py
├── config.py
├── fetcher.py
│   ├── cache.py
│   └── logging_utils.py
├── optimizer.py
│   └── config.py
├── searxng.py
├── security.py
├── extractors/
│   ├── base.py
│   ├── trafilatura.py
│   ├── readability.py
│   └── custom.py
├── llm/
│   ├── client.py
│   ├── config.py
│   └── embeddings.py
└── research/
    ├── pipeline.py
    ├── citations.py
    ├── chunker.py
    └── reranking.py
```

## Thread Safety

- Connection pool uses global singleton pattern
- LRU cache is thread-safe for read operations
- Rate limiter uses time-based sliding window

## Error Handling

```python
class FetchError(Exception):
    # Raised when URL fetching fails

class SearXNGError(Exception):
    # Raised when search fails

class LLMError(Exception):
    # Raised when LLM operations fail
```

## Extensibility

### Adding a New Extractor

1. Create `extractors/new_extractor.py`:
```python
from .base import ContentExtractor, ExtractedContent

class NewExtractor(ContentExtractor):
    name = "new_extractor"
    
    async def extract(self, html: str, url: str) -> ExtractedContent:
        # Implementation
```

2. Register in `extractors/__init__.py`:
```python
from .new_extractor import NewExtractor

__all__ = [..., "NewExtractor"]
```

### Adding a New Search Provider

1. Create `search_providers/new_provider.py`
2. Implement search interface
3. Register in server.py
