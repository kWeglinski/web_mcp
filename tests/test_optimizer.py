"""Unit tests for the optimizer module."""

import pytest

from web_mcp.optimizer import (
    estimate_tokens,
    optimize_content,
    truncate_text,
)


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
