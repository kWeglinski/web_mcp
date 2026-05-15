import re

from bs4 import BeautifulSoup


class ContentCleaner:
    """Handles cleaning of HTML content to produce structured text."""

    def clean(self, html_content: str) -> str:
        """
        Cleans HTML content by removing redundant elements and converting
        headings to markdown-style markers for easier chunking.

        Args:
            html_content: The raw HTML string to clean.

        Returns:
            A cleaned text string with markdown-style headings.
        """
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Remove redundant elements
        for element in soup(["script", "style", "header", "footer", "nav", "aside"]):
            element.decompose()

        # 2. Convert headings to markdown-style markers
        # We do this by iterating through all elements and replacing heading tags
        # with their markdown equivalents before stripping other tags.
        for i in range(1, 7):
            for heading in soup.find_all(f"h{i}"):
                heading.replace_with(f"\n{'#' * i} {heading.get_text().strip()}\n")

        # 3. Get text content
        # Using get_text(separator="\n") helps preserve some structure
        text = soup.get_text(separator="\n")

        # 4. Normalize whitespace
        # Replace multiple newlines with a standard amount
        text = re.sub(r"\n\s*\n", "\n\n", text)
        # Remove leading/trailing whitespace from each line
        lines = [line.strip() for line in text.split("\n")]
        # Rejoin and remove excessive whitespace within lines if necessary,
        # but keep enough to distinguish paragraphs.
        text = "\n".join(lines)

        # Final cleanup of multiple empty lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()


class SemanticChunker:
    """Handles chunking of text based on structural markers."""

    def chunk(self, text: str, max_chunk_size: int = 1000) -> list[str]:
        """
        Splits text into chunks based on heading structures and paragraph breaks.

        Args:
            text: The cleaned text to chunk.
            max_chunk_size: Maximum number of characters per chunk.

        Returns:
            A list of text chunks.
        """
        if not text:
            return []

        # Split by headings (Markdown style #, ##, etc.)
        # This regex looks for lines starting with one or more '#'
        sections = re.split(r"\n(?=#+ )", text)

        chunks: list[str] = []

        for section in sections:
            section = section.strip()
            if not section:
                continue

            if len(section) <= max_chunk_size:
                chunks.append(section)
            else:
                # Section is too large, sub-split by paragraphs (double newline)
                paragraphs = re.split(r"\n\s*\n", section)
                current_chunk: list[str] = []
                current_length = 0

                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue

                    # Length of paragraph + potential newline if added to current_chunk
                    para_len = len(para)
                    # Add 2 for the '\n\n' separator if it's not the first para in chunk
                    added_len = para_len + (2 if current_chunk else 0)

                    if current_length + added_len <= max_chunk_size:
                        current_chunk.append(para)
                        current_length += added_len
                    else:
                        # Flush current chunk if it exists
                        if current_chunk:
                            chunks.append("\n\n".join(current_chunk))

                        # If a single paragraph is still larger than max_chunk_size,
                        # we must hard-split it by lines or characters.
                        if para_len > max_chunk_size:
                            # Hard split by character count
                            for i in range(0, para_len, max_chunk_size):
                                chunks.append(para[i : i + max_chunk_size])
                            current_chunk = []
                            current_length = 0
                        else:
                            # Start a new chunk with this paragraph
                            current_chunk = [para]
                            current_length = para_len

                # Final flush for the section
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))

        return chunks
