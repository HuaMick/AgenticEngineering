#!/bin/bash
set -e

# MyAgents Global Installation Script
# ====================================
# This script builds a wheel and installs myagents globally using uv tool install.
# This makes 'myagents' globally accessible without needing to activate a virtual environment.
#
# Prerequisites:
# - uv package manager installed (https://astral.sh/uv)
# - gcloud CLI installed and authenticated (gcloud auth login)
# - Python 3.11+
#
# The script automatically:
# - Configures authentication for GCP Artifact Registry via netrc
# - Fetches agent-gcptoolkit dependency from the registry
# - Installs myagents as a globally accessible CLI tool

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/dist"

# GCP Artifact Registry configuration
GCP_ARTIFACT_REGISTRY="https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/"
GCP_ARTIFACT_HOST="us-central1-python.pkg.dev"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Setup netrc authentication for GCP Artifact Registry
# This allows uv to authenticate with the registry using gcloud credentials
setup_netrc_auth() {
    print_info "Configuring netrc authentication for GCP Artifact Registry..."

    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Install it from: https://cloud.google.com/sdk/docs/install"
        return 1
    fi

    # Get access token from gcloud
    local TOKEN
    TOKEN=$(gcloud auth print-access-token 2>/dev/null)
    if [ -z "$TOKEN" ]; then
        print_error "Failed to get GCP access token. Please run: gcloud auth login"
        return 1
    fi

    # Create or update ~/.netrc with GCP Artifact Registry credentials
    local NETRC_FILE="$HOME/.netrc"
    local NETRC_ENTRY="machine $GCP_ARTIFACT_HOST login oauth2accesstoken password $TOKEN"

    # Remove existing entry for this host if present
    if [ -f "$NETRC_FILE" ]; then
        # Create temp file without the old entry
        grep -v "machine $GCP_ARTIFACT_HOST" "$NETRC_FILE" > "$NETRC_FILE.tmp" 2>/dev/null || true
        mv "$NETRC_FILE.tmp" "$NETRC_FILE"
    fi

    # Add new entry
    echo "$NETRC_ENTRY" >> "$NETRC_FILE"
    chmod 600 "$NETRC_FILE"

    print_info "netrc authentication configured for $GCP_ARTIFACT_HOST"
    return 0
}

echo "========================================="
echo "MyAgents Global Installation (uv tool)"
echo "========================================="
echo ""
echo "This will build a wheel and install myagents globally."
echo "Reference: https://docs.astral.sh/uv/concepts/tools/"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    print_error "uv is not installed. Install it from: https://astral.sh/uv"
    exit 1
fi

# Navigate to project root
cd "$PROJECT_ROOT"

# Check if wheel already exists
WHEEL_PATH=$(ls "$BUILD_DIR"/myagents-*.whl 2>/dev/null | head -n1)

if [ -z "$WHEEL_PATH" ]; then
    print_info "No wheel found. Building package..."
    
    # Clean previous build artifacts
    print_info "Cleaning previous build artifacts..."
    rm -rf build dist *.egg-info
    
    # Build the wheel
    print_info "Building wheel..."
    if ! uv build --out-dir dist/; then
        print_error "Failed to build wheel"
        exit 1
    fi
    
    # Get the newly built wheel
    WHEEL_PATH=$(ls "$BUILD_DIR"/myagents-*.whl 2>/dev/null | head -n1)
    
    if [ -z "$WHEEL_PATH" ]; then
        print_error "Wheel was not created in $BUILD_DIR"
        exit 1
    fi
else
    print_info "Found existing wheel: $WHEEL_PATH"
    print_warning "Using existing wheel. Run 'uv build --out-dir dist/' to rebuild."
fi

echo ""

# Setup netrc authentication for GCP Artifact Registry
if ! setup_netrc_auth; then
    print_error "Failed to setup authentication"
    exit 1
fi

echo ""
print_info "Installing wheel globally: $WHEEL_PATH"

# Install globally using uv tool install
# --index: Add GCP Artifact Registry to resolve agent-gcptoolkit dependency
# Authentication is handled via ~/.netrc (configured by setup_netrc_auth)
print_info "Using GCP Artifact Registry: $GCP_ARTIFACT_REGISTRY"
if ! uv tool install --force \
    --index "$GCP_ARTIFACT_REGISTRY" \
    "$WHEEL_PATH"; then
    print_error "Failed to install wheel globally"
    echo ""
    print_warning "Troubleshooting steps:"
    print_warning "  1. Ensure GCP authentication is configured:"
    print_warning "     gcloud auth login"
    print_warning "  2. Re-run this script to refresh the authentication token"
    print_warning "  3. Verify agent-gcptoolkit is on the registry:"
    print_warning "     pip index versions agent-gcptoolkit --index-url $GCP_ARTIFACT_REGISTRY"
    exit 1
fi

echo ""
print_info "Updating shell configuration..."
uv tool update-shell

echo ""
echo "========================================="
echo -e "${GREEN}Installation Complete!${NC}"
echo "========================================="
echo ""
echo "The 'myagents' command is now globally accessible."
echo ""
echo "Verify installation:"
echo "  cd /tmp && myagents --version"
echo ""
echo "Note: If 'myagents' is not found, you may need to:"
echo "  1. Restart your shell (to reload PATH)"
echo "  2. Or run: source ~/.bashrc (or ~/.zshrc)"
echo ""
echo "UV installs tools to: ~/.local/bin (Unix) or %USERPROFILE%\\.local\\bin (Windows)"
echo ""

