"""Unit tests for Kiwix content processing."""

from web_mcp.kiwix_processor import ContentCleaner, SemanticChunker


class TestContentCleaner:
    def test_clean_empty_string(self):
        cleaner = ContentCleaner()
        assert cleaner.clean("") == ""

    def test_clean_none(self):
        cleaner = ContentCleaner()
        assert cleaner.clean(None) == ""

    def test_clean_removes_scripts(self):
        cleaner = ContentCleaner()
        html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
        result = cleaner.clean(html)
        assert "alert" not in result
        assert "Hello" in result
        assert "World" in result

    def test_clean_removes_styles(self):
        cleaner = ContentCleaner()
        html = "<style>body { color: red; }</style><p>Content</p>"
        result = cleaner.clean(html)
        assert "color: red" not in result
        assert "Content" in result

    def test_clean_removes_header(self):
        cleaner = ContentCleaner()
        html = "<header>Nav</header><p>Main</p>"
        result = cleaner.clean(html)
        assert "Nav" not in result
        assert "Main" in result

    def test_clean_removes_footer(self):
        cleaner = ContentCleaner()
        html = "<p>Body</p><footer>Footer text</footer>"
        result = cleaner.clean(html)
        assert "Body" in result
        assert "Footer" not in result

    def test_clean_removes_nav(self):
        cleaner = ContentCleaner()
        html = "<nav>Links</nav><article>Content</article>"
        result = cleaner.clean(html)
        assert "Links" not in result
        assert "Content" in result

    def test_clean_removes_aside(self):
        cleaner = ContentCleaner()
        html = "<aside>Sidebar</aside><p>Main content</p>"
        result = cleaner.clean(html)
        assert "Sidebar" not in result
        assert "Main content" in result

    def test_clean_converts_h1(self):
        cleaner = ContentCleaner()
        html = "<h1>Big Title</h1><p>Content</p>"
        result = cleaner.clean(html)
        assert "# Big Title" in result

    def test_clean_converts_h2(self):
        cleaner = ContentCleaner()
        html = "<h2>Subtitle</h2><p>Content</p>"
        result = cleaner.clean(html)
        assert "## Subtitle" in result

    def test_clean_converts_h3(self):
        cleaner = ContentCleaner()
        html = "<h3>Small Title</h3><p>Content</p>"
        result = cleaner.clean(html)
        assert "### Small Title" in result

    def test_clean_converts_all_heading_levels(self):
        cleaner = ContentCleaner()
        html = "<h1>H1</h1><h2>H2</h2><h3>H3</h3><h4>H4</h4><h5>H5</h5><h6>H6</h6>"
        result = cleaner.clean(html)
        assert "# H1" in result
        assert "## H2" in result
        assert "### H3" in result
        assert "#### H4" in result
        assert "##### H5" in result
        assert "###### H6" in result

    def test_clean_normalizes_whitespace(self):
        cleaner = ContentCleaner()
        html = "<p>Para1</p>\n\n\n\n<p>Para2</p>"
        result = cleaner.clean(html)
        assert "\n\n\n" not in result

    def test_clean_preserves_paragraphs(self):
        cleaner = ContentCleaner()
        html = "<p>First paragraph</p><p>Second paragraph</p>"
        result = cleaner.clean(html)
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_clean_strips_lines(self):
        cleaner = ContentCleaner()
        html = "<p>  Spaced content  </p>"
        result = cleaner.clean(html)
        assert "  " not in result

    def test_clean_with_complex_html(self):
        cleaner = ContentCleaner()
        html = """
        <html>
            <head><title>Test</title></head>
            <body>
                <header>Header content</header>
                <nav>Nav links</nav>
                <article>
                    <h1>Main Title</h1>
                    <p>Article content here.</p>
                    <script>bad script</script>
                </article>
                <aside>Sidebar</aside>
                <footer>Footer</footer>
            </body>
        </html>
        """
        result = cleaner.clean(html)
        assert "Header content" not in result
        assert "Nav links" not in result
        assert "Sidebar" not in result
        assert "Footer" not in result
        assert "bad script" not in result
        assert "# Main Title" in result
        assert "Article content here" in result


class TestSemanticChunker:
    def test_chunk_empty_text(self):
        chunker = SemanticChunker()
        assert chunker.chunk("") == []

    def test_chunk_none_text(self):
        chunker = SemanticChunker()
        assert chunker.chunk(None) == []

    def test_chunk_single_section(self):
        chunker = SemanticChunker()
        text = "# Section 1\n\nSome content here."
        result = chunker.chunk(text, max_chunk_size=1000)
        assert len(result) == 1
        assert "# Section 1" in result[0]

    def test_chunk_multiple_sections(self):
        chunker = SemanticChunker()
        text = "# Section 1\n\nContent 1.\n\n## Subsection\n\nMore content.\n\n# Section 2\n\nContent 2."
        result = chunker.chunk(text, max_chunk_size=1000)
        assert len(result) >= 2

    def test_chunk_splits_large_sections(self):
        chunker = SemanticChunker()
        long_content = "A" * 2000
        text = f"# Big Section\n\n{long_content}"
        result = chunker.chunk(text, max_chunk_size=500)
        assert len(result) >= 4  # 2000 chars / 500 = 4 chunks

    def test_chunk_respects_max_chunk_size(self):
        chunker = SemanticChunker()
        text = "# Section\n\n" + "X" * 100
        result = chunker.chunk(text, max_chunk_size=50)
        for chunk in result:
            assert len(chunk) <= 50 or "X" * 51 not in chunk

    def test_chunk_splits_by_paragraphs(self):
        chunker = SemanticChunker()
        text = "# Section\n\nPara 1.\n\nPara 2.\n\nPara 3."
        result = chunker.chunk(text, max_chunk_size=30)
        assert len(result) >= 2

    def test_chunk_hard_splits_over_paragraph(self):
        chunker = SemanticChunker()
        single_para = "P" * 200
        text = f"# Section\n\n{single_para}"
        result = chunker.chunk(text, max_chunk_size=50)
        assert len(result) >= 4  # 200 / 50 = 4

    def test_chunk_preserves_heading_markers(self):
        chunker = SemanticChunker()
        text = "# Heading 1\n\nContent\n\n## Heading 2\n\nMore content"
        result = chunker.chunk(text, max_chunk_size=500)
        assert any("# Heading 1" in chunk for chunk in result)
        assert any("## Heading 2" in chunk for chunk in result)

    def test_chunk_skips_empty_sections(self):
        chunker = SemanticChunker()
        text = "\n\n# Section\n\nContent\n\n\n"
        result = chunker.chunk(text, max_chunk_size=1000)
        assert len(result) >= 1

    def test_chunk_default_max_size(self):
        chunker = SemanticChunker()
        text = "# Section\n\nSmall content"
        result = chunker.chunk(text)
        assert len(result) == 1

    def test_chunk_large_text_with_multiple_headings(self):
        chunker = SemanticChunker()
        sections = "\n\n".join([f"## Section {i}\n\n{'C' * 100}" for i in range(5)])
        result = chunker.chunk(sections, max_chunk_size=200)
        assert len(result) >= 5

    def test_chunk_section_under_max_size(self):
        chunker = SemanticChunker()
        text = "# Small\n\nShort"
        result = chunker.chunk(text, max_chunk_size=1000)
        assert len(result) == 1
        assert result[0] == "# Small\n\nShort"
