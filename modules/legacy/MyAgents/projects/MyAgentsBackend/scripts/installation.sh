#!/usr/bin/env bash
set -e

# MyAgents Installation Script
# =============================
# This script is for INITIAL INSTALLATION ONLY (one-time setup).
# For subsequent updates, use: myagents update/rebuild
#
# What this script does:
# - Installs uv package manager (if not present)
# - Creates Python virtual environment
# - Installs dependencies
# - Installs myagents package in editable mode
# - Sets up environment variables
# - Verifies installation
#
# Prerequisites:
# - Python 3.11+
# - GCP project with Secret Manager API enabled
# - Gemini API key stored in GCP Secret Manager

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "========================================="
echo "MyAgents Installation Script"
echo "========================================="
echo ""
echo "Project root: $PROJECT_ROOT"
echo ""

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check Python version
print_info "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"; then
    print_error "Python 3.11+ is required. Found: $python_version"
    exit 1
fi
print_info "Python version OK: $python_version"

# Check if uv is installed
print_info "Checking for uv package manager..."
if ! command -v uv &> /dev/null; then
    print_warning "uv not found. Installing uv..."

    # Download installer to temporary file for verification
    UV_INSTALLER=$(mktemp)
    trap "rm -f $UV_INSTALLER" EXIT

    if ! curl -LsSf https://astral.sh/uv/install.sh -o "$UV_INSTALLER"; then
        print_error "Failed to download uv installer"
        exit 1
    fi

    # Verify the installer is a shell script
    if ! file "$UV_INSTALLER" | grep -q "shell script\|text"; then
        print_error "Downloaded file is not a valid shell script"
        exit 1
    fi

    # Run the installer
    if ! sh "$UV_INSTALLER"; then
        print_error "Failed to execute uv installer"
        exit 1
    fi

    # Source the shell configuration to get uv in PATH
    if [ -f "$HOME/.cargo/env" ]; then
        source "$HOME/.cargo/env"
    fi

    # Verify installation
    if ! command -v uv &> /dev/null; then
        print_error "Failed to install uv. Please install manually: https://astral.sh/uv"
        exit 1
    fi
    print_info "uv installed successfully"
else
    print_info "uv is already installed"
fi

# Navigate to project root
cd "$PROJECT_ROOT"

# Create virtual environment
print_info "Creating virtual environment..."
if [ -d ".venv" ]; then
    print_warning "Virtual environment already exists. Skipping creation."
else
    uv venv
    print_info "Virtual environment created"
fi

# Install dependencies
print_info "Installing dependencies..."
uv sync
print_info "Dependencies installed"

# Install package in editable mode
print_info "Installing myagents package in editable mode..."
uv pip install -e .
print_info "Package installed"

# Check for GCP project environment variable
print_info "Checking environment configuration..."
if [ -z "$GCP_PROJECT_ID" ]; then
    print_warning "GCP_PROJECT_ID not set"
    echo ""
    echo "To use MyAgents, you need to set your GCP project ID:"
    echo "  export GCP_PROJECT_ID=\"your-gcp-project-id\""
    echo ""
    echo "Add this to your shell configuration file (~/.bashrc, ~/.zshrc, etc.)"
    echo "to make it permanent."
else
    print_info "GCP_PROJECT_ID is set: $GCP_PROJECT_ID"
fi

# Verify installation
print_info "Verifying installation..."
if uv run myagents --help &> /dev/null; then
    print_info "Installation verified successfully"
else
    print_error "Installation verification failed"
    exit 1
fi

echo ""
echo "========================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Set your GCP project ID (if not already set):"
echo "   export GCP_PROJECT_ID=\"your-gcp-project-id\""
echo ""
echo "2. Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "3. Try the CLI:"
echo "   myagents --help"
echo "   myagents chat"
echo ""
echo "4. For subsequent updates, use CLI commands:"
echo "   myagents update    # Update package"
echo "   myagents rebuild   # Rebuild package"
echo ""
echo "For more information, see:"
echo "  - README.md"
echo "  - docs/setup.md"
echo ""
echo "========================================="
echo ""

# Note about one-time use
print_warning "NOTE: This script is for INITIAL INSTALLATION ONLY"
print_warning "For updates and rebuilds, use 'myagents update' or 'myagents rebuild'"
