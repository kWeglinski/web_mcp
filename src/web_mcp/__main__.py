"""Main entry point for running the MCP server."""

import sys
from .server import main, SERVER_HOST, SERVER_PORT

if __name__ == "__main__":
    try:
        # Check if --http or other transport flags are passed
        if "--http" in sys.argv or "--streamable-http" in sys.argv:
            print(f"Starting MCP server on http://{SERVER_HOST}:{SERVER_PORT}")
            print("Tools available:")
            print("  - fetch_url")
            print("  - fetch_url_simple")
            print("  - web_search")
        main()
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        sys.exit(1)
