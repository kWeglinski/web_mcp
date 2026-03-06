"""Trafilatura-based content extractor."""

import trafilatura

from .base import ContentExtractor, ExtractedContent


class TrafilaturaExtractor(ContentExtractor):
    """Content extractor using Trafilatura library."""

    name = "trafilatura"

    async def extract(self, html: str, url: str) -> ExtractedContent:
        """Extract content using Trafilatura.

        Args:
            html: Raw HTML content
            url: Source URL

        Returns:
            ExtractedContent with title, author, date, language, text, and metadata
        """
        # Extract content with Trafilatura
        result = trafilatura.extract(
            html,
            include_comments=False,
            include_links=False,
            output_format="json",
        )

        if not result:
            # Fallback to basic extraction
            return ExtractedContent(
                title=None,
                author=None,
                date=None,
                language=None,
                text="",
                url=url,
                metadata={},
            )

        # Parse the JSON result
        import json

        data = json.loads(result) if isinstance(result, str) else result

        return ExtractedContent(
            title=data.get("title"),
            author=data.get("author"),
            date=data.get("date"),
            language=data.get("language"),
            text=data.get("text", ""),
            url=url,
            metadata={
                "url": url,
                "extractor": self.name,
                "raw_data": data,
            },
        )
