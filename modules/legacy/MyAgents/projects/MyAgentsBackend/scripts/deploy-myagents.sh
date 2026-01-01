#!/bin/bash
# Deploy MyAgents package to Google Artifact Registry
# This is a convenience wrapper around deploy-to-registry.sh

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}[INFO]${NC} Deploying MyAgents package to Artifact Registry..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
REGISTRY_NAME="myagents-python"
PACKAGE_DIR="/home/code/myagents/MyAgents-packaging-001"
PROJECT_ID="myagents-475112"

# Verify package directory exists
if [ ! -d "$PACKAGE_DIR" ]; then
    echo -e "${YELLOW}[WARN]${NC} Package directory not found at: $PACKAGE_DIR"
    echo -e "${YELLOW}[WARN]${NC} Please update PACKAGE_DIR in this script if the location is different"
    exit 1
fi

# Call the main deployment script
"$SCRIPT_DIR/deploy-to-registry.sh" "$REGISTRY_NAME" "$PACKAGE_DIR" "$PROJECT_ID"

exit $?
