"""Main entry point for running the MCP server."""

import sys

from .logging_utils import get_logger
from .server import SERVER_HOST, SERVER_PORT, main

logger = get_logger(__name__)

if __name__ == "__main__":
    try:
        # Check if --http or other transport flags are passed
        if "--http" in sys.argv or "--streamable-http" in sys.argv:
            logger.info(f"Starting MCP server on http://{SERVER_HOST}:{SERVER_PORT}")
            logger.info("Tools available:")
            logger.info("  - fetch_url")
            logger.info("  - fetch_url_simple")
            logger.info("  - web_search")
        main()
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)
