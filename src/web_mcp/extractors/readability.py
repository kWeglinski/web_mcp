"""Readability-based content extractor."""

from bs4 import BeautifulSoup

from .base import ContentExtractor, ExtractedContent


class ReadabilityExtractor(ContentExtractor):
    """Content extractor using Readability algorithm.

    Note: This uses a simplified implementation since the readability library
    has limited API. For production use, consider using trafilatura which has
    better built-in readability features.
    """

    name = "readability"

    async def extract(self, html: str, url: str) -> ExtractedContent:
        """Extract content using simplified Readability algorithm.

        Args:
            html: Raw HTML content
            url: Source URL

        Returns:
            ExtractedContent with title, author, date, language, text, and metadata
        """
        # Use BeautifulSoup to extract main content
        soup = BeautifulSoup(html, "html.parser")

        # Try to find article tag or main content
        article = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_=["content", "article", "post"])
        )

        if article:
            # Remove scripts and styles
            for script in article(["script", "style"]):
                script.decompose()

            # Try to find title
            title = None
            h1 = article.find("h1")
            if h1:
                title = h1.get_text(strip=True)

            # Get text content
            text = article.get_text(separator=" ", strip=True)
        else:
            # Fallback: just get text from body
            title_elem = soup.find("h1") or soup.find("title")
            title = title_elem.get_text(strip=True) if title_elem else None
            text = soup.get_text(separator=" ", strip=True)

        return ExtractedContent(
            title=title,
            author=None,
            date=None,
            language=None,
            text=text,
            url=url,
            metadata={
                "url": url,
                "extractor": self.name,
            },
        )
