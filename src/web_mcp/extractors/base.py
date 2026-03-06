"""Base classes for content extractors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExtractedContent:
    """Result of content extraction."""

    title: str | None
    author: str | None
    date: str | None
    language: str | None
    text: str
    url: str
    metadata: dict


class ContentExtractor(ABC):
    """Abstract base class for content extractors."""

    @abstractmethod
    async def extract(self, html: str, url: str) -> ExtractedContent:
        """Extract content from HTML.

        Args:
            html: Raw HTML content
            url: Source URL

        Returns:
            ExtractedContent with title, author, date, language, text, and metadata
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Extractor name."""
        pass
