# Chart Rendering Enhancement Plan

## Overview
Enhance the charting tool to support multiple output formats (HTML, URL, image) and add a general-purpose HTML rendering tool with secure, time-limited content serving.

## Problem
The model cannot render HTML directly. We need:
1. A way to serve HTML content via URLs that can be viewed in browsers
2. Chart output as images (base64) for direct embedding
3. Authentication to secure the exposed endpoints

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  MCP Tool       │────▶│  Content Store   │────▶│  HTTP Endpoint  │
│  (render_html)  │     │  (LRU + TTL)     │     │  /c/{hash}      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                        │
                        ┌──────────────────┐            │
                        │  Token Auth      │◀───────────┘
                        │  (optional)      │
                        └──────────────────┘
```

## Implementation Plan

### 1. Add Dependencies
**File**: `pyproject.toml`

Add `kaleido` for Plotly image export:
```toml
"kaleido>=0.2.0",
```

### 2. Configuration
**File**: `src/web_mcp/config.py`

Add new environment variables:
- `WEB_MCP_PUBLIC_URL` - Public URL of the MCP server (e.g., `https://mcp.example.com`)
- `WEB_MCP_AUTH_TOKEN` - Bearer token for securing content endpoints (optional)
- `WEB_MCP_CONTENT_TTL` - TTL for stored content in seconds (default: 3600 = 1 hour)

### 3. Content Storage Module
**File**: `src/web_mcp/content_store.py`

In-memory content storage with:
- Unique hash-based keys (URL-safe)
- TTL-based expiration (default 1 hour)
- LRU eviction when capacity reached
- Thread-safe operations

```python
class ContentStore:
    def store(content: str, content_type: str = "text/html") -> str:
        """Store content, return unique hash ID"""
        
    def get(hash_id: str) -> Optional[StoredContent]:
        """Retrieve content by hash, None if expired/not found"""
        
    def delete(hash_id: str) -> bool:
        """Delete content by hash"""
```

### 4. Custom HTTP Routes
**File**: `src/web_mcp/server.py`

Add custom routes using `@mcp.custom_route()`:

```python
@mcp.custom_route("/c/{content_id}", methods=["GET"])
async def serve_content(request: Request) -> Response:
    """Serve stored content by ID with optional token auth"""
```

**Authentication**:
- If `WEB_MCP_AUTH_TOKEN` is set, require `Authorization: Bearer <token>` header
- Return 401 if token missing/invalid
- Skip auth if token not configured (development mode)

### 5. New Tool: `render_html`
**File**: `src/web_mcp/server.py`

```python
@mcp.tool()
async def render_html(
    html: str = Field(description="HTML content to render"),
    content_type: str = Field(
        default="text/html",
        description="Content MIME type (text/html, text/css, application/javascript)"
    ),
) -> str:
    """Store HTML/CSS/JS content and return a viewable URL.
    
    Content is stored for 1 hour with a unique URL.
    Requires WEB_MCP_PUBLIC_URL to be configured.
    
    Returns:
        Full URL to view the content, or error message
    """
```

### 6. Enhanced `create_chart_tool`
**File**: `src/web_mcp/server.py`

Add `output` parameter:

```python
@mcp.tool()
async def create_chart_tool(
    type: str = Field(...),
    data: dict = Field(...),
    title: str = Field(default=""),
    x_label: str = Field(default=""),
    y_label: str = Field(default=""),
    options: dict = Field(default_factory=dict),
    output: str = Field(
        default="html",
        description="Output format: 'html' (raw HTML), 'url' (viewable link), 'image' (base64 PNG)"
    ),
) -> str:
    """Create an interactive Plotly chart.
    
    Output formats:
    - html: Returns full HTML with embedded Plotly (default)
    - url: Stores chart and returns viewable URL (requires WEB_MCP_PUBLIC_URL)
    - image: Returns base64-encoded PNG image (for direct embedding)
    """
```

### 7. Update Charts Generator
**File**: `src/web_mcp/charts/generator.py`

Add image export method:

```python
def create_chart_image(config: ChartConfig, format: str = "png") -> str:
    """Create chart and return as base64-encoded image"""
    fig = create_figure(config)
    img_bytes = fig.to_image(format=format, width=800, height=600)
    return base64.b64encode(img_bytes).decode('utf-8')
```

## File Changes Summary

| File | Changes |
|------|---------|
| `pyproject.toml` | Add `kaleido>=0.2.0` |
| `src/web_mcp/config.py` | Add `public_url`, `auth_token`, `content_ttl` config |
| `src/web_mcp/content_store.py` | **NEW** - Content storage with TTL |
| `src/web_mcp/server.py` | Add custom route `/c/{id}`, `render_html` tool, enhance `create_chart_tool` |
| `src/web_mcp/charts/generator.py` | Add `create_chart_image()` function |

## Environment Variables

```bash
# Required for URL output
WEB_MCP_PUBLIC_URL=https://mcp.example.com

# Optional - secures content endpoints
WEB_MCP_AUTH_TOKEN=your-secret-token-here

# Optional - content TTL in seconds (default: 3600)
WEB_MCP_CONTENT_TTL=3600
```

## Usage Examples

### Render HTML
```
Tool: render_html
Input: {"html": "<html><body><h1>Hello World</h1></body></html>"}
Output: "https://mcp.example.com/c/a1b2c3d4e5f6"
```

### Create Chart as URL
```
Tool: create_chart_tool
Input: {
    "type": "bar",
    "data": {"x": ["A", "B", "C"], "y": [10, 20, 15]},
    "title": "Sales",
    "output": "url"
}
Output: "https://mcp.example.com/c/xyz123abc"
```

### Create Chart as Image
```
Tool: create_chart_tool
Input: {
    "type": "pie",
    "data": {"labels": ["A", "B"], "values": [60, 40]},
    "output": "image"
}
Output: "data:image/png;base64,iVBORw0KGgo..."
```

## Security Considerations

1. **Token Authentication**: Optional bearer token protects content endpoints when exposed
2. **Time-Limited**: Content expires after TTL (default 1 hour)
3. **Hash-Based IDs**: Content IDs are SHA-256 hashes, not guessable
4. **No Directory Traversal**: Hash IDs are validated before lookup
5. **Content Size Limits**: Consider adding max content size (e.g., 10MB)

## Implementation Order

1. Add `kaleido` dependency to `pyproject.toml`
2. Add config options to `config.py`
3. Create `content_store.py` module
4. Add custom route `/c/{content_id}` to `server.py`
5. Add `render_html` tool
6. Add image export to `charts/generator.py`
7. Enhance `create_chart_tool` with `output` parameter
8. Test all output formats
9. Run `uv run pytest` to verify

## Testing

- Test content storage and retrieval
- Test TTL expiration
- Test token authentication (with and without)
- Test all chart output formats
- Test image generation for each chart type
