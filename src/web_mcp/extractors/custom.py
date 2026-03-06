"""Custom selector-based content extractor using BeautifulSoup."""

from bs4 import BeautifulSoup

from .base import ContentExtractor, ExtractedContent


class CustomSelectorExtractor(ContentExtractor):
    """Content extractor using custom CSS selectors.

    This extractor allows you to specify custom selectors for extracting
    content from specific websites or patterns.

    Example configuration:
        {
            "title_selector": "h1, .article-title",
            "content_selector": ".article-content, main",
            "author_selector": ".author, .byline",
            "date_selector": ".publish-date, time"
        }
    """

    name = "custom"

    def __init__(
        self,
        title_selector: str = "h1",
        content_selector: str = "article, .content, main",
        author_selector: str | None = None,
        date_selector: str | None = None,
    ):
        """Initialize the custom selector extractor.

        Args:
            title_selector: CSS selector for page title
            content_selector: CSS selector for main content
            author_selector: Optional CSS selector for author
            date_selector: Optional CSS selector for publication date
        """
        self.title_selector = title_selector
        self.content_selector = content_selector
        self.author_selector = author_selector
        self.date_selector = date_selector

    async def extract(self, html: str, url: str) -> ExtractedContent:
        """Extract content using custom CSS selectors.

        Args:
            html: Raw HTML content
            url: Source URL

        Returns:
            ExtractedContent with title, author, date, language, text, and metadata
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = None
        title_elem = soup.select_one(self.title_selector)
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Extract content
        text = ""
        content_elem = soup.select_one(self.content_selector)
        if content_elem:
            # Remove scripts and styles
            for script in content_elem(["script", "style"]):
                script.decompose()
            text = content_elem.get_text(separator=" ", strip=True)

        # Extract author
        author = None
        if self.author_selector:
            author_elem = soup.select_one(self.author_selector)
            if author_elem:
                author = author_elem.get_text(strip=True)

        # Extract date
        date = None
        if self.date_selector:
            date_elem = soup.select_one(self.date_selector)
            if date_elem:
                date = date_elem.get_text(strip=True)

        return ExtractedContent(
            title=title,
            author=author,
            date=date,
            language=None,
            text=text,
            url=url,
            metadata={
                "url": url,
                "extractor": self.name,
                "selectors": {
                    "title": self.title_selector,
                    "content": self.content_selector,
                    "author": self.author_selector,
                    "date": self.date_selector,
                },
            },
        )
