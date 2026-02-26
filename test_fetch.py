"""Test script to verify the fetch_url tool works."""
import asyncio
import pytest
from src.web_mcp.fetcher import fetch_url, FetchError
from src.web_mcp.config import Config
from src.web_mcp.extractors.trafilatura import TrafilaturaExtractor


@pytest.mark.asyncio
async def test_fetch():
    """Test fetching and extracting content from a URL."""
    config = Config()
    
    # Test with a simple URL
    test_url = "https://example.com"
    
    print(f"Testing fetch from: {test_url}")
    
    try:
        # Fetch HTML
        html = await fetch_url(test_url, config)
        print(f"✓ Fetched {len(html)} bytes")
        
        # Extract content
        extractor = TrafilaturaExtractor()
        extracted = await extractor.extract(html, test_url)
        
        print(f"\nExtracted content:")
        print(f"Title: {extracted.title}")
        print(f"Author: {extracted.author}")
        print(f"Date: {extracted.date}")
        print(f"Language: {extracted.language}")
        print(f"\nText preview (first 200 chars):\n{extracted.text[:200]}...")
        
    except FetchError as e:
        print(f"Fetch error: {e}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_fetch())
