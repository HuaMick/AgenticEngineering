#!/bin/bash
set -e

PROJECT_ROOT="/home/code/myagents/Agent-GCPtoolkit"
BUILD_DIR="$PROJECT_ROOT/build-artifacts"

echo "=== Installing agent-gcptoolkit with UV (Alternative Method) ==="
echo ""
echo "NOTE: This installs into a virtual environment."
echo "After installation, you MUST activate the venv to use 'myagents':"
echo "  source .venv/bin/activate"
echo ""
echo "For a global installation that doesn't require venv activation,"
echo "use ./scripts/install-global.sh instead (RECOMMENDED)."
echo ""
read -p "Continue with UV installation? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation cancelled."
    echo "Run ./scripts/install-global.sh for recommended installation."
    exit 0
fi

# Check if wheel exists
WHEEL_PATH=$(ls "$BUILD_DIR/dist"/agent_gcptoolkit-*.whl 2>/dev/null | head -n1)

if [ -z "$WHEEL_PATH" ]; then
    echo "Error: No wheel found in $BUILD_DIR/dist/"
    echo "Run ./scripts/build.sh first"
    exit 1
fi

echo "Installing: $WHEEL_PATH"
uv pip install --force-reinstall "$WHEEL_PATH"

echo ""
echo "=== Installation complete ==="
echo ""
echo "IMPORTANT: To use the myagents CLI, activate the virtual environment:"
echo "  source .venv/bin/activate"
echo ""
echo "Then verify with: myagents --version"
echo ""
echo "To make 'myagents' globally accessible without venv activation,"
echo "use UV tool install instead: ./scripts/install-global.sh"
