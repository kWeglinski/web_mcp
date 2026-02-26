# Extractors Guide

## Overview

The Web Browsing MCP Server supports multiple content extraction strategies. Each extractor has its own strengths and use cases.

## Available Extractors

### 1. Trafilatura Extractor ([`trafilatura.py`](../src/web_mcp/extractors/trafilatura.py))

The default extractor using the Trafilatura library for high-quality content extraction.

**Features:**
- High accuracy content extraction
- Metadata extraction (title, author, date, language)
- Comment removal
- Link preservation

**Configuration:**
```python
from web_mcp.extractors.trafilatura import TrafilaturaExtractor

extractor = TrafilaturaExtractor()
result = await extractor.extract(html, url)
```

**Use Cases:**
- General web page extraction
- Article extraction with metadata
- Content where accuracy is critical

### 2. Readability Extractor ([`readability.py`](../src/web_mcp/extractors/readability.py))

Article-focused extraction using Readability algorithm.

**Features:**
- Optimized for article content
- Clean text extraction
- Title detection

**Configuration:**
```python
from web_mcp.extractors.readability import ReadabilityExtractor

extractor = ReadabilityExtractor()
result = await extractor.extract(html, url)
```

**Use Cases:**
- News articles
- Blog posts
- Long-form content

### 3. Custom Selector Extractor ([`custom.py`](../src/web_mcp/extractors/custom.py))

Custom CSS selector-based extraction for specific websites.

**Features:**
- Custom CSS selectors
- Title, author, date selectors
- Content selector

**Configuration:**
```python
from web_mcp.extractors.custom import CustomSelectorExtractor

extractor = CustomSelectorExtractor(
    title_selector="h1",
    author_selector=".author",
    date_selector=".date",
    content_selector=".article-content"
)
result = await extractor.extract(html, url)
```

**Use Cases:**
- Specific website structures
- Custom extraction requirements
- Testing

## Base Extractor Interface

All extractors implement the `ContentExtractor` interface:

```python
class ContentExtractor(ABC):
    name: str
    
    @abstractmethod
    async def extract(self, html: str, url: str) -> ExtractedContent:
        """Extract content from HTML.
        
        Args:
            html: Raw HTML content
            url: Source URL
            
        Returns:
            ExtractedContent with title, author, date, language, text
        """
```

## Extractor Selection

### Via Environment Variable

```bash
WEB_MCP_DEFAULT_EXTRACTOR=trafilatura  # or readability, custom
```

### Via Tool Parameter

```python
# Use Trafilatura (default)
result = await fetch_url(url, extractor="trafilatura")

# Use Readability
result = await fetch_url(url, extractor="readability")

# Use Custom
result = await fetch_url(url, extractor="custom")
```

## ExtractedContent Structure

```python
@dataclass
class ExtractedContent:
    title: Optional[str]       # Page title
    author: Optional[str]      # Author name
    date: Optional[str]        # Publication date
    language: Optional[str]    # Detected language
    text: str                  # Extracted content
    url: str                   # Source URL
    metadata: dict             # Additional metadata
```

## Custom Extractor Implementation

### Step 1: Create Extractor Class

```python
from web_mcp.extractors.base import ContentExtractor, ExtractedContent
from bs4 import BeautifulSoup

class MyExtractor(ContentExtractor):
    name = "my_extractor"
    
    async def extract(self, html: str, url: str) -> ExtractedContent:
        soup = BeautifulSoup(html, "html.parser")
        
        # Extract title
        title_tag = soup.find("h1")
        title = title_tag.get_text() if title_tag else None
        
        # Extract author
        author_tag = soup.find(class_="author")
        author = author_tag.get_text() if author_tag else None
        
        # Extract content
        content_tag = soup.find(class_="article-content")
        text = content_tag.get_text() if content_tag else ""
        
        return ExtractedContent(
            title=title,
            author=author,
            date=None,
            language=None,
            text=text,
            url=url,
            metadata={}
        )
```

### Step 2: Register Extractor

```python
# src/web_mcp/extractors/__init__.py
from .my_extractor import MyExtractor

__all__ = [
    "TrafilaturaExtractor",
    "ReadabilityExtractor",
    "CustomSelectorExtractor",
    "MyExtractor",  # Add your extractor
]
```

## Extractor Comparison

| Feature | Trafilatura | Readability | Custom |
|---------|-------------|-------------|--------|
| Accuracy | High | Medium | Variable |
| Metadata | Yes | Limited | Custom |
| Speed | Fast | Fast | Fast |
| Flexibility | Low | Medium | High |
| Best For | General use | Articles | Specific sites |

## Troubleshooting

### No Content Extracted
- Check if the HTML is valid
- Try a different extractor
- Verify CSS selectors (for custom)

### Metadata Missing
- Some pages don't have metadata
- Try different extractor
- Check if page requires JavaScript ( Trafilatura doesn't execute JS)

### Wrong Content Extracted
- Verify URL is correct
- Try different extractor
- Check for dynamic content (may need JS execution)

## Best Practices

1. **Use Trafilatura** for general-purpose extraction
2. **Use Readability** for article-focused content
3. **Use Custom** when you need specific selectors
4. **Test extractors** on your target sites
5. **Handle missing metadata** gracefully in your code
