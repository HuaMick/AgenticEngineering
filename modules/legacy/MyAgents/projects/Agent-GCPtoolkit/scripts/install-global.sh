#!/bin/bash
set -e

PROJECT_ROOT="/home/code/myagents/Agent-GCPtoolkit"
BUILD_DIR="$PROJECT_ROOT/build-artifacts"

echo "=== Installing agent-gcptoolkit globally with UV (RECOMMENDED) ==="
echo ""
echo "This method makes 'myagents' globally accessible without"
echo "needing to activate a virtual environment."
echo ""
echo "Reference: https://docs.astral.sh/uv/concepts/tools/"
echo ""

# Check if wheel exists
WHEEL_PATH=$(ls "$BUILD_DIR/dist"/agent_gcptoolkit-*.whl 2>/dev/null | head -n1)

if [ -z "$WHEEL_PATH" ]; then
    echo "Error: No wheel found in $BUILD_DIR/dist/"
    echo "Run ./scripts/build.sh first"
    exit 1
fi

echo "Installing: $WHEEL_PATH"
uv tool install --force "$WHEEL_PATH"

echo ""
echo "=== Ensuring PATH is configured ==="
uv tool update-shell

echo ""
echo "=== Installation complete ==="
echo ""
echo "The 'myagents' command is now globally accessible."
echo "Verify with: myagents --version"
echo ""
echo "Note: If 'myagents' is not found, you may need to:"
echo "  1. Restart your shell (to reload PATH)"
echo "  2. Or run: source ~/.bashrc (or ~/.zshrc)"
echo ""
echo "UV installs tools to: ~/.local/bin (Unix) or %USERPROFILE%\\.local\\bin (Windows)"
