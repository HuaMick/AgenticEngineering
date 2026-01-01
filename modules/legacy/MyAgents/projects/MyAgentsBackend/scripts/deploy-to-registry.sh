#!/bin/bash
# Deploy Python package to Google Artifact Registry
# Usage: ./deploy-to-registry.sh REGISTRY_NAME PACKAGE_DIR PROJECT_ID

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check required parameters
if [ "$#" -ne 3 ]; then
    log_error "Usage: $0 REGISTRY_NAME PACKAGE_DIR PROJECT_ID"
    log_error "Example: $0 myagents-python /home/code/myagents/MyAgents-packaging-001 myagents-475112"
    exit 1
fi

REGISTRY_NAME="$1"
PACKAGE_DIR="$2"
PROJECT_ID="$3"
LOCATION="us-central1"

# Validate parameters
if [ -z "$REGISTRY_NAME" ]; then
    log_error "REGISTRY_NAME cannot be empty"
    exit 1
fi

if [ -z "$PACKAGE_DIR" ]; then
    log_error "PACKAGE_DIR cannot be empty"
    exit 1
fi

if [ ! -d "$PACKAGE_DIR" ]; then
    log_error "PACKAGE_DIR does not exist: $PACKAGE_DIR"
    exit 1
fi

if [ -z "$PROJECT_ID" ]; then
    log_error "PROJECT_ID cannot be empty"
    exit 1
fi

# Check for required tools
log_info "Checking for required tools..."
for tool in gcloud uv twine; do
    if ! command -v $tool &> /dev/null; then
        log_error "$tool is not installed or not in PATH"
        exit 1
    fi
done

log_info "Required tools found: gcloud, uv, twine"

# Change to package directory
log_info "Changing to package directory: $PACKAGE_DIR"
cd "$PACKAGE_DIR" || exit 1

# Verify pyproject.toml exists
if [ ! -f "pyproject.toml" ]; then
    log_error "pyproject.toml not found in $PACKAGE_DIR"
    exit 1
fi

# Extract package name and version from pyproject.toml
log_info "Extracting package information from pyproject.toml..."
PACKAGE_NAME=$(grep -E "^name\s*=" pyproject.toml | sed -E 's/name\s*=\s*"([^"]+)".*/\1/')
PACKAGE_VERSION=$(grep -E "^version\s*=" pyproject.toml | sed -E 's/version\s*=\s*"([^"]+)".*/\1/')

if [ -z "$PACKAGE_NAME" ]; then
    log_error "Could not extract package name from pyproject.toml"
    exit 1
fi

if [ -z "$PACKAGE_VERSION" ]; then
    log_error "Could not extract package version from pyproject.toml"
    exit 1
fi

log_info "Package: $PACKAGE_NAME"
log_info "Version: $PACKAGE_VERSION"

# Clean previous build artifacts
log_info "Cleaning previous build artifacts..."
if [ -d "dist" ]; then
    rm -rf dist
    log_info "Removed existing dist/ directory"
fi

# Build the package
log_info "Building package with uv..."
if ! uv build --out-dir dist/; then
    log_error "Package build failed"
    exit 1
fi

log_info "Package built successfully"

# List built artifacts
log_info "Built artifacts:"
ls -lh dist/

# Verify artifacts were created
if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
    log_error "No build artifacts found in dist/"
    exit 1
fi

# Configure gcloud project
log_info "Configuring gcloud project: $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

# Verify registry exists
log_info "Verifying registry exists: $REGISTRY_NAME in $LOCATION"
if ! gcloud artifacts repositories describe "$REGISTRY_NAME" --location="$LOCATION" &> /dev/null; then
    log_error "Registry $REGISTRY_NAME does not exist in $LOCATION"
    log_error "Please create it first with:"
    log_error "gcloud artifacts repositories create $REGISTRY_NAME --repository-format=python --location=$LOCATION"
    exit 1
fi

log_info "Registry verified successfully"

# Upload to Artifact Registry using twine
log_info "Uploading to Artifact Registry using twine..."

# Set up repository URL
REPO_URL="https://$LOCATION-python.pkg.dev/$PROJECT_ID/$REGISTRY_NAME/"

# Use gcloud to get the access token and configure twine
log_info "Configuring authentication..."
export TWINE_USERNAME="oauth2accesstoken"
export TWINE_PASSWORD="$(gcloud auth print-access-token)"
export TWINE_REPOSITORY_URL="$REPO_URL"

# Upload using twine
if ! twine upload --repository-url "$REPO_URL" dist/*; then
    log_error "Upload to Artifact Registry failed"
    exit 1
fi

log_info "Upload successful!"

# Validate the upload
log_info "Validating upload..."
if gcloud artifacts packages list \
    --repository="$REGISTRY_NAME" \
    --location="$LOCATION" \
    --format="value(name)" | grep -q "$PACKAGE_NAME"; then
    log_info "Package $PACKAGE_NAME successfully uploaded to $REGISTRY_NAME"

    # List versions
    log_info "Available versions:"
    gcloud artifacts versions list \
        --package="$PACKAGE_NAME" \
        --repository="$REGISTRY_NAME" \
        --location="$LOCATION" \
        --format="table(name,createTime)" || true
else
    log_warn "Could not verify package in registry (it may take a moment to appear)"
fi

# Summary
echo ""
log_info "=========================================="
log_info "Deployment Summary"
log_info "=========================================="
log_info "Package:     $PACKAGE_NAME"
log_info "Version:     $PACKAGE_VERSION"
log_info "Registry:    $REGISTRY_NAME"
log_info "Location:    $LOCATION"
log_info "Project:     $PROJECT_ID"
log_info "=========================================="
echo ""

log_info "To install this package, use:"
echo "pip install --extra-index-url https://$LOCATION-python.pkg.dev/$PROJECT_ID/$REGISTRY_NAME/simple/ $PACKAGE_NAME"

exit 0
