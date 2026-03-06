"""Unit tests for content extractors."""

from unittest.mock import patch

import pytest

from web_mcp.extractors.base import ExtractedContent
from web_mcp.extractors.custom import CustomSelectorExtractor
from web_mcp.extractors.readability import ReadabilityExtractor
from web_mcp.extractors.trafilatura import TrafilaturaExtractor


class TestTrafilaturaExtractor:
    """Tests for TrafilaturaExtractor."""

    @pytest.mark.asyncio
    async def test_extract_success(self):
        """Test successful extraction with trafilatura."""
        extractor = TrafilaturaExtractor()

        html = """
        <!DOCTYPE html>
        <html>
            <head><title>Test Page</title></head>
            <body>
                <article>
                    <h1>Test Title</h1>
                    <p>This is test content.</p>
                </article>
            </body>
        </html>
        """

        with patch("web_mcp.extractors.trafilatura.trafilatura") as mock_trafilatura:
            mock_trafilatura.extract.return_value = (
                '{"title": "Test Title", "text": "This is test content.", '
                '"author": "John Doe", "date": "2024-01-01", "language": "en"}'
            )

            result = await extractor.extract(html, "https://example.com")

            assert result.title == "Test Title"
            assert result.text == "This is test content."
            assert result.author == "John Doe"
            assert result.date == "2024-01-01"
            assert result.language == "en"

    @pytest.mark.asyncio
    async def test_extract_empty_result(self):
        """Test extraction with empty result."""
        extractor = TrafilaturaExtractor()

        html = "<html><body>Test</body></html>"

        with patch("web_mcp.extractors.trafilatura.trafilatura") as mock_trafilatura:
            mock_trafilatura.extract.return_value = None

            result = await extractor.extract(html, "https://example.com")

            assert result.title is None
            assert result.author is None
            assert result.date is None
            assert result.language is None
            assert result.text == ""

    @pytest.mark.asyncio
    async def test_extract_json_string(self):
        """Test extraction with JSON string result."""
        extractor = TrafilaturaExtractor()

        html = "<html><body>Test</body></html>"

        with patch("web_mcp.extractors.trafilatura.trafilatura") as mock_trafilatura:
            mock_trafilatura.extract.return_value = '{"title": "Test", "text": "Content"}'

            result = await extractor.extract(html, "https://example.com")

            assert result.title == "Test"
            assert result.text == "Content"

    @pytest.mark.asyncio
    async def test_extract_dict_result(self):
        """Test extraction with dict result."""
        extractor = TrafilaturaExtractor()

        html = "<html><body>Test</body></html>"

        with patch("web_mcp.extractors.trafilatura.trafilatura") as mock_trafilatura:
            mock_trafilatura.extract.return_value = {
                "title": "Test",
                "text": "Content",
                "author": "Author",
            }

            result = await extractor.extract(html, "https://example.com")

            assert result.title == "Test"
            assert result.text == "Content"

    @pytest.mark.asyncio
    async def test_name_property(self):
        """Test extractor name property."""
        extractor = TrafilaturaExtractor()
        assert extractor.name == "trafilatura"


class TestReadabilityExtractor:
    """Tests for ReadabilityExtractor."""

    @pytest.mark.asyncio
    async def test_extract_with_article_tag(self):
        """Test extraction with article tag."""
        extractor = ReadabilityExtractor()

        html = """
        <!DOCTYPE html>
        <html>
            <body>
                <article>
                    <h1>Article Title</h1>
                    <p>Article content here.</p>
                </article>
            </body>
        </html>
        """

        result = await extractor.extract(html, "https://example.com")

        assert result.title == "Article Title"
        assert "Article content" in result.text

    @pytest.mark.asyncio
    async def test_extract_with_main_tag(self):
        """Test extraction with main tag."""
        extractor = ReadabilityExtractor()

        html = """
        <!DOCTYPE html>
        <html>
            <body>
                <main>
                    <h1>Main Content</h1>
                    <p>Some text.</p>
                </main>
            </body>
        </html>
        """

        result = await extractor.extract(html, "https://example.com")

        assert result.title == "Main Content"
        assert "Some text" in result.text

    @pytest.mark.asyncio
    async def test_extract_fallback(self):
        """Test extraction with fallback to body."""
        extractor = ReadabilityExtractor()

        html = """
        <!DOCTYPE html>
        <html>
            <body>
                <h1>Fallback Title</h1>
                <p>Content without article tag.</p>
            </body>
        </html>
        """

        result = await extractor.extract(html, "https://example.com")

        assert result.title == "Fallback Title"
        assert "Content without article tag" in result.text

    @pytest.mark.asyncio
    async def test_extract_removes_scripts_and_styles(self):
        """Test that scripts and styles are removed."""
        extractor = ReadabilityExtractor()

        html = """
        <!DOCTYPE html>
        <html>
            <body>
                <article>
                    <h1>Title</h1>
                    <p>Content</p>
                    <script>alert('bad');</script>
                    <style>.class { color: red; }</style>
                </article>
            </body>
        </html>
        """

        result = await extractor.extract(html, "https://example.com")

        assert "alert" not in result.text
        assert ".class" not in result.text

    @pytest.mark.asyncio
    async def test_name_property(self):
        """Test extractor name property."""
        extractor = ReadabilityExtractor()
        assert extractor.name == "readability"


class TestCustomSelectorExtractor:
    """Tests for CustomSelectorExtractor."""

    @pytest.mark.asyncio
    async def test_extract_with_custom_selectors(self):
        """Test extraction with custom selectors."""
        extractor = CustomSelectorExtractor(
            title_selector=".custom-title",
            content_selector=".custom-content",
        )

        html = """
        <!DOCTYPE html>
        <html>
            <body>
                <div class="custom-title">Custom Title</div>
                <div class="custom-content">
                    <p>Custom content.</p>
                </div>
            </body>
        </html>
        """

        result = await extractor.extract(html, "https://example.com")

        assert result.title == "Custom Title"
        assert "Custom content" in result.text

    @pytest.mark.asyncio
    async def test_extract_with_author_selector(self):
        """Test extraction with author selector."""
        extractor = CustomSelectorExtractor(
            title_selector="h1",
            content_selector=".content",
            author_selector=".author",
        )

        html = """
        <!DOCTYPE html>
        <html>
            <body>
                <h1>Page Title</h1>
                <div class="author">John Doe</div>
                <div class="content">
                    <p>Content here.</p>
                </div>
            </body>
        </html>
        """

        result = await extractor.extract(html, "https://example.com")

        assert result.author == "John Doe"

    @pytest.mark.asyncio
    async def test_extract_with_date_selector(self):
        """Test extraction with date selector."""
        extractor = CustomSelectorExtractor(
            title_selector="h1",
            content_selector=".content",
            date_selector=".date",
        )

        html = """
        <!DOCTYPE html>
        <html>
            <body>
                <h1>Page Title</h1>
                <time class="date">2024-01-01</time>
                <div class="content">
                    <p>Content here.</p>
                </div>
            </body>
        </html>
        """

        result = await extractor.extract(html, "https://example.com")

        assert result.date == "2024-01-01"

    @pytest.mark.asyncio
    async def test_extract_no_author_or_date(self):
        """Test extraction without author or date."""
        extractor = CustomSelectorExtractor(
            title_selector="h1",
            content_selector=".content",
        )

        html = """
        <!DOCTYPE html>
        <html>
            <body>
                <h1>Page Title</h1>
                <div class="content">
                    <p>Content here.</p>
                </div>
            </body>
        </html>
        """

        result = await extractor.extract(html, "https://example.com")

        assert result.author is None
        assert result.date is None

    @pytest.mark.asyncio
    async def test_name_property(self):
        """Test extractor name property."""
        extractor = CustomSelectorExtractor()
        assert extractor.name == "custom"


class TestExtractedContent:
    """Tests for ExtractedContent dataclass."""

    def test_extracted_content_fields(self):
        """Test ExtractedContent has all required fields."""
        content = ExtractedContent(
            title="Title",
            author="Author",
            date="Date",
            language="en",
            text="Text",
            url="https://example.com",
            metadata={"key": "value"},
        )

        assert content.title == "Title"
        assert content.author == "Author"
        assert content.date == "Date"
        assert content.language == "en"
        assert content.text == "Text"
        assert content.url == "https://example.com"
        assert content.metadata == {"key": "value"}
