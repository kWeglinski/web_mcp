# Tool Cleanup Plan

## Summary
1. Remove 3 tools: `ask`, `ask_stream`, `web_search`
2. Rename 4 tools
3. Merge 3 fetch tools into single `get_page` tool

## Changes

### 1. Remove Tools
Delete these tools from `server.py`:
- `ask` (lines 564-621)
- `ask_stream` (lines 624-673)
- `web_search` (lines 482-523)

Also remove unused imports:
- `from web_mcp.research.pipeline import research, research_stream, ResearchResult`
- `from web_mcp.research.citations import Source`
- `from web_mcp.llm.config import get_llm_config`

Remove `AskResult` class (lines 557-561)

### 2. Rename Tools
| Old Name | New Name |
|----------|----------|
| `create_chart_tool` | `generate_chart` |
| `current_datetime` | `get_date` |
| `web_search_simple` | `search_web` |

### 3. Merge Fetch Tools into `get_page`

**Current tools being merged:**
- `fetch_url` - full page with metadata, returns `FetchResult`
- `fetch_url_simple` - text only, returns `str`
- `fetch_url_query` - BM25-ranked chunks, returns `str`

**New unified `get_page` tool:**

```python
@mcp.tool()
async def get_page(
    url: str = Field(description="The URL to fetch"),
    mode: str = Field(
        default="simple",
        description="Fetch mode: 'simple' (text only), 'full' (with metadata), 'query' (relevant chunks only)"
    ),
    query: str = Field(
        default="",
        description="Search query - required when mode='query', finds relevant chunks using BM25"
    ),
    max_tokens: int = Field(
        default=120000,
        description="Maximum tokens to return (for 'simple' and 'full' modes)"
    ),
    max_chunks: int = Field(
        default=5,
        description="Maximum chunks to return (for 'query' mode)"
    ),
    include_metadata: bool = Field(
        default=True,
        description="Include title, author, date in output (for 'full' mode)"
    ),
    extractor: str = Field(
        default="trafilatura",
        description="Extractor: 'trafilatura', 'readability', or 'custom' (for 'full' mode)"
    ),
    render: str = Field(
        default="auto",
        description="Render mode: 'auto' (httpx + playwright fallback), 'playwright' (force browser), 'httpx' (static only)"
    ),
) -> str:
    """Fetch and extract content from a URL.
    
    Modes:
    - simple: Returns just the text content (fastest)
    - full: Returns text with metadata (title, author, date, language)
    - query: Returns only chunks relevant to your search query using BM25 ranking
    
    Use 'simple' for quick text extraction.
    Use 'full' when you need article metadata.
    Use 'query' when looking for specific information on a large page.
    """
```

### 4. Update FastMCP Instructions
Update the server instructions to reflect new tool names:

```python
mcp = FastMCP(
    name="web-browsing",
    instructions="A web browsing MCP server with content extraction and chart generation. "
                 "Use `get_page` to fetch web content, "
                 "`search_web` to search the web, "
                 "`generate_chart` to create visualizations.",
    ...
)
```

### 5. Update main() Tools List
```python
tools = "get_page, search_web, generate_chart, get_date, render_html, health"
```

## Final Tool List
After cleanup, the server will have these tools:
1. `get_page` - unified page fetching
2. `search_web` - web search (renamed from `web_search_simple`)
3. `generate_chart` - chart creation (renamed from `create_chart_tool`)
4. `get_date` - date/time (renamed from `current_datetime`)
5. `render_html` - render HTML content
6. `health` - server health check

## Files Modified
- `src/web_mcp/server.py` - all changes
