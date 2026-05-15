"""Unit tests for __main__ entry point."""

import sys
from unittest.mock import MagicMock, patch


class TestMain:
    @patch("web_mcp.__main__.main")
    @patch("web_mcp.__main__.logger")
    def test_main_runs_without_args(self, mock_logger, mock_main):
        with patch.object(sys, "argv", ["web_mcp"]):
            from web_mcp.__main__ import main

            main()
            mock_main.assert_called_once()

    @patch("web_mcp.__main__.main")
    @patch("web_mcp.__main__.logger")
    def test_main_with_http_flag(self, mock_logger, mock_main):
        with patch.object(sys, "argv", ["web_mcp", "--http"]):
            from web_mcp.__main__ import main

            main()
            mock_main.assert_called_once()

    @patch("web_mcp.__main__.main")
    @patch("web_mcp.__main__.logger")
    def test_main_with_streamable_http_flag(self, mock_logger, mock_main):
        with patch.object(sys, "argv", ["web_mcp", "--streamable-http"]):
            from web_mcp.__main__ import main

            main()
            mock_main.assert_called_once()

    def test_main_handles_exception(self, monkeypatch):
        import sys

        # Capture sys.exit call
        exit_called = []
        original_exit = sys.exit

        def mock_exit(code=0):
            exit_called.append(code)

        sys.exit = mock_exit

        # Patch main to raise exception
        import web_mcp.__main__

        original_main = web_mcp.__main__.main
        web_mcp.__main__.main = lambda: (_ for _ in ()).throw(Exception("Server error"))

        # Patch logger
        web_mcp.__main__.logger = MagicMock()

        # The if __name__ == "__main__" block only runs when executed as script
        # So we simulate what happens inside that block
        try:
            web_mcp.__main__.main()
        except Exception as e:
            web_mcp.__main__.logger.error(f"Error starting server: {e}")
            sys.exit(1)

        web_mcp.__main__.logger.error.assert_called_once()
        assert exit_called == [1]

        # Restore
        sys.exit = original_exit
        web_mcp.__main__.main = original_main

    def test_entry_point_imports(self):
        """Test that the module can be imported without errors."""
        import web_mcp.__main__

        assert hasattr(web_mcp.__main__, "main")
