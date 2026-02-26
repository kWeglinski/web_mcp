#!/bin/bash
# Setup script for web-mcp - installs uv and all dependencies

set -e  # Exit on error

echo "=== Web MCP Setup Script ==="
echo ""

# Step 1: Install uv (if not already installed)
if ! command -v uv &> /dev/null; then
    echo "Step 1: Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Add uv to PATH immediately for current session
    export PATH="$HOME/.local/bin:$PATH"
    
    # Also persist it in .zshrc (default on macOS)
    if [[ "$SHELL" == *"zsh"* ]]; then
        if ! grep -q 'export PATH="\$HOME/.local/bin:\$PATH"' ~/.zshrc 2>/dev/null; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
        fi
    fi
    
    # Also persist for bash
    if [[ "$SHELL" == *"bash"* ]]; then
        if ! grep -q 'export PATH="\$HOME/.local/bin:\$PATH"' ~/.bash_profile 2>/dev/null; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bash_profile
        fi
    fi
    
    echo "uv installed successfully!"
else
    echo "Step 1: uv is already installed."
fi
echo ""

# Step 2: Install Python 3.12 (as specified in .python-version)
echo "Step 2: Installing Python 3.12..."
uv python install 3.12
echo "Python 3.12 installed!"
echo ""

# Step 3: Sync dependencies from uv.lock
echo "Step 3: Syncing dependencies..."
uv sync
echo "Dependencies synced successfully!"
echo ""

# Step 4: Verify installation
echo "Step 4: Verifying installation..."
uv run python -c "import web_mcp; print('web_mcp imported successfully!')"
echo ""

echo "=== Setup Complete ==="
echo "You can now run the server with: uv run python -m web_mcp.server"
echo "Or run tests with: uv run pytest"
