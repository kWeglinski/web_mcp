"""Unit tests for the optimizer module."""

import pytest

from web_mcp.optimizer import (
    _simple_truncate,
    _smart_truncate,
    estimate_tokens,
    optimize_content,
    truncate_text,
)


class TestSimpleTruncate:
    """Tests for _simple_truncate function."""

    def test_simple_truncate_basic(self):
        """Test basic simple truncation."""
        text = "a" * 100
        result = _simple_truncate(text, 0.5)
        assert len(result) == 50
        assert result == "a" * 50

    def test_simple_truncate_empty_string(self):
        """Test empty string."""
        result = _simple_truncate("", 0.5)
        assert result == ""

    def test_simple_truncate_full_ratio(self):
        """Test with ratio of 1.0 (no truncation)."""
        text = "Hello world"
        result = _simple_truncate(text, 1.0)
        assert result == text

    def test_simple_truncate_zero_ratio(self):
        """Test with ratio of 0.0."""
        text = "Hello world"
        result = _simple_truncate(text, 0.0)
        assert result == ""

    def test_simple_truncate_small_ratio(self):
        """Test with very small ratio."""
        text = "a" * 1000
        result = _simple_truncate(text, 0.01)
        assert len(result) == 10

    def test_simple_truncate_preserves_start(self):
        """Test that simple truncation preserves the start of text."""
        text = "Hello world, this is a test"
        result = _simple_truncate(text, 0.5)
        assert result.startswith("Hello")


class TestSmartTruncate:
    """Tests for _smart_truncate function."""

    def test_smart_truncate_basic(self):
        """Test basic smart truncation with paragraphs."""
        text = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
        result = _smart_truncate(text, 0.5)
        assert "Paragraph 1" in result
        assert "Paragraph 3" not in result

    def test_smart_truncate_empty_string(self):
        """Test empty string."""
        result = _smart_truncate("", 0.5)
        assert result == ""

    def test_smart_truncate_single_paragraph(self):
        """Test with single paragraph."""
        text = "Single paragraph content"
        result = _smart_truncate(text, 0.5)
        assert result == text

    def test_smart_truncate_full_ratio(self):
        """Test with ratio of 1.0 (no truncation)."""
        text = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
        result = _smart_truncate(text, 1.0)
        assert result == text

    def test_smart_truncate_zero_ratio(self):
        """Test with ratio of 0.0 - should keep at least one paragraph."""
        text = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
        result = _smart_truncate(text, 0.0)
        assert "Paragraph 1" in result

    def test_smart_truncate_keeps_first_paragraph(self):
        """Test that smart truncation keeps first paragraph."""
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = _smart_truncate(text, 0.33)
        assert "First paragraph" in result
        assert "Third paragraph" not in result

    def test_smart_truncate_multiple_newlines(self):
        """Test with multiple newlines between paragraphs."""
        text = "Para 1.\n\n\n\nPara 2.\n\n\nPara 3."
        result = _smart_truncate(text, 0.5)
        assert "Para 1" in result
        assert "Para 3" not in result

    def test_smart_truncate_no_paragraphs(self):
        """Test with text that has no double newlines."""
        text = "Single line text without paragraphs"
        result = _smart_truncate(text, 0.5)
        assert result == text

    def test_smart_truncate_unicode(self):
        """Test with unicode content."""
        text = "First paragraph with émojis 🎉\n\nSecond paragraph 日本語\n\nThird paragraph"
        result = _smart_truncate(text, 0.5)
        assert "émojis" in result or "日本語" in result

    def test_smart_truncate_ratio_greater_than_one(self):
        """Test with ratio > 1.0."""
        text = "Paragraph 1.\n\nParagraph 2."
        result = _smart_truncate(text, 2.0)
        assert result == text


class TestEstimateTokens:
    """Tests for estimate_tokens function."""

    def test_estimate_tokens_basic(self):
        """Test basic token estimation."""
        text = "Hello world"
        # 11 characters / 4 = 2 tokens (integer division)
        assert estimate_tokens(text) == 2

    def test_estimate_tokens_empty(self):
        """Test empty string."""
        assert estimate_tokens("") == 0

    def test_estimate_tokens_none(self):
        """Test None input."""
        assert estimate_tokens(None) == 0

    def test_estimate_tokens_long_text(self):
        """Test longer text."""
        text = "a" * 100
        assert estimate_tokens(text) == 25

    def test_estimate_tokens_special_chars(self):
        """Test text with special characters."""
        text = "Hello! How are you? I'm fine."
        assert estimate_tokens(text) == 7


class TestTruncateText:
    """Tests for truncate_text function."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        from web_mcp.config import Config

        config = Config()
        return config

    def test_truncate_text_no_truncation_needed(self, mock_config):
        """Test when truncation is not needed."""
        text = "Hello world"
        max_tokens = 100
        result = truncate_text(text, max_tokens, mock_config)
        assert result == text

    def test_truncate_text_simple_strategy(self, mock_config):
        """Test simple truncation strategy."""
        text = "a" * 100
        mock_config.truncation_strategy = "simple"
        result = truncate_text(text, 10, mock_config)
        # 10 tokens * 4 chars = 40 chars
        assert len(result) <= 40

    def test_truncate_text_smart_strategy(self, mock_config):
        """Test smart truncation strategy."""
        text = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
        mock_config.truncation_strategy = "smart"
        result = truncate_text(text, 10, mock_config)
        # Should keep first paragraph
        assert "Paragraph 1" in result

    def test_truncate_text_empty(self, mock_config):
        """Test empty string."""
        result = truncate_text("", 100, mock_config)
        assert result == ""

    def test_truncate_text_none(self, mock_config):
        """Test None input."""
        result = truncate_text(None, 100, mock_config)
        assert result is None

    def test_truncate_text_very_short_string(self, mock_config):
        """Test with very short string that doesn't need truncation."""
        text = "Hi"
        result = truncate_text(text, 100, mock_config)
        assert result == text

    def test_truncate_text_exact_token_limit(self, mock_config):
        """Test when text is exactly at token limit."""
        text = "a" * 400  # 100 tokens
        result = truncate_text(text, 100, mock_config)
        assert result == text

    def test_truncate_text_slightly_over_limit(self, mock_config):
        """Test when text is slightly over token limit."""
        text = "a" * 404  # 101 tokens
        mock_config.truncation_strategy = "simple"
        result = truncate_text(text, 100, mock_config)
        assert len(result) < len(text)

    def test_truncate_text_unicode_simple(self, mock_config):
        """Test unicode text with simple strategy."""
        text = "Hello 世界 🌍 " * 50
        mock_config.truncation_strategy = "simple"
        result = truncate_text(text, 10, mock_config)
        assert len(result) <= 40

    def test_truncate_text_unicode_smart(self, mock_config):
        """Test unicode text with smart strategy."""
        text = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        mock_config.truncation_strategy = "smart"
        result = truncate_text(text, 5, mock_config)
        assert "第一段" in result

    def test_truncate_text_no_config_uses_default(self):
        """Test that None config uses default config."""
        text = "Hello world"
        result = truncate_text(text, 100, None)
        assert result == text

    def test_truncate_text_preserves_content_start(self, mock_config):
        """Test that truncation preserves start of content."""
        text = "Important header\n\nBody content\n\nFooter"
        mock_config.truncation_strategy = "smart"
        result = truncate_text(text, 5, mock_config)
        assert result.startswith("Important")

    def test_truncate_text_whitespace_only(self, mock_config):
        """Test with whitespace only content."""
        text = "   \n\n   \n\n   "
        mock_config.truncation_strategy = "smart"
        result = truncate_text(text, 5, mock_config)
        assert result is not None

    def test_truncate_text_mixed_newlines(self, mock_config):
        """Test with mixed newline patterns."""
        text = "Para 1\n\nPara 2\r\n\r\nPara 3"
        mock_config.truncation_strategy = "smart"
        result = truncate_text(text, 5, mock_config)
        assert "Para 1" in result


class TestOptimizeContent:
    """Tests for optimize_content function."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        from web_mcp.config import Config

        config = Config()
        return config

    def test_optimize_content_no_truncation(self, mock_config):
        """Test optimization when no truncation needed."""
        text = "Hello world"
        result = optimize_content(text, 100, mock_config)

        assert result["text"] == text
        assert not result["optimization_info"]["truncated"]
        assert result["optimization_info"]["original_tokens"] == 2

    def test_optimize_content_with_truncation(self, mock_config):
        """Test optimization with truncation."""
        text = "a" * 500
        mock_config.truncation_strategy = "simple"
        result = optimize_content(text, 10, mock_config)

        assert result["optimization_info"]["truncated"] is True
        assert result["optimization_info"]["original_tokens"] == 125

    def test_optimize_content_empty(self, mock_config):
        """Test empty string."""
        result = optimize_content("", 100, mock_config)

        assert result["text"] == ""
        assert not result["optimization_info"]["truncated"]

    def test_optimize_content_returns_correct_keys(self, mock_config):
        """Test that result has correct keys."""
        text = "Hello world"
        result = optimize_content(text, 100, mock_config)

        assert "text" in result
        assert "optimization_info" in result
        assert "original_tokens" in result["optimization_info"]
        assert "truncated" in result["optimization_info"]

    def test_optimize_content_none_input(self, mock_config):
        """Test None input."""
        result = optimize_content(None, 100, mock_config)
        assert result["text"] is None
        assert result["optimization_info"]["original_tokens"] == 0
        assert not result["optimization_info"]["truncated"]

    def test_optimize_content_unicode(self, mock_config):
        """Test with unicode content."""
        text = "Hello 世界 🌍 " * 100
        mock_config.truncation_strategy = "simple"
        result = optimize_content(text, 10, mock_config)
        assert result["optimization_info"]["truncated"] is True

    def test_optimize_content_truncated_tokens_in_result(self, mock_config):
        """Test that truncated_tokens is in result when truncated."""
        text = "a" * 500
        mock_config.truncation_strategy = "simple"
        result = optimize_content(text, 10, mock_config)
        assert "truncated_tokens" in result["optimization_info"]
        assert result["optimization_info"]["truncated_tokens"] < result["optimization_info"]["original_tokens"]

    def test_optimize_content_no_truncated_tokens_when_not_truncated(self, mock_config):
        """Test that truncated_tokens is not in result when not truncated."""
        text = "Hello world"
        result = optimize_content(text, 100, mock_config)
        assert "truncated_tokens" not in result["optimization_info"]

    def test_optimize_content_no_config_uses_default(self):
        """Test that None config uses default config."""
        text = "Hello world"
        result = optimize_content(text, 100, None)
        assert result["text"] == text

    def test_optimize_content_very_large_text(self, mock_config):
        """Test with very large text."""
        text = "a" * 10000
        mock_config.truncation_strategy = "simple"
        result = optimize_content(text, 100, mock_config)
        assert result["optimization_info"]["truncated"] is True
        assert len(result["text"]) < len(text)

    def test_optimize_content_smart_strategy(self, mock_config):
        """Test with smart strategy."""
        text = "Para 1.\n\nPara 2.\n\nPara 3.\n\nPara 4.\n\nPara 5."
        mock_config.truncation_strategy = "smart"
        result = optimize_content(text, 5, mock_config)
        assert result["optimization_info"]["truncated"] is True
        assert "Para 1" in result["text"]

    def test_optimize_content_preserves_structure(self, mock_config):
        """Test that optimization preserves structure info."""
        text = "Header\n\nBody\n\nFooter"
        mock_config.truncation_strategy = "smart"
        result = optimize_content(text, 2, mock_config)
        assert "Header" in result["text"]
