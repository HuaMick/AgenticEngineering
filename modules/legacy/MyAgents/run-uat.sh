#!/bin/bash
# UAT Test Runner Script
# Run User Acceptance Tests using docker-compose.uat.yml
# Usage: ./run-uat.sh [OPTIONS]

set -e

# Default values
WORKTREE_NAME="${WORKTREE_NAME:-MyAgents-cloud-deploy}"
GCP_SA_KEY_PATH="${GCP_SA_KEY_PATH:-/home/code/myagents/secrets/myagents-475112-60da581cc8d9.json}"
UAT_RESULTS_DIR="${UAT_RESULTS_DIR:-./uat-results}"
CLEANUP="${CLEANUP:-true}"
BUILD="${BUILD:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Print usage
usage() {
    cat <<EOF
UAT Test Runner

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -b, --build             Build images before running tests
    -nc, --no-cleanup       Don't cleanup containers after tests
    -w, --worktree NAME     Worktree name (default: MyAgents-cloud-deploy)
    -k, --key-path PATH     GCP service account key path
    -r, --results-dir DIR   Test results directory (default: ./uat-results)

Environment Variables:
    WORKTREE_NAME          Override worktree name
    GCP_SA_KEY_PATH        Override GCP service account path
    UAT_RESULTS_DIR        Override results directory
    CLEANUP                Set to 'false' to skip cleanup
    BUILD                  Set to 'true' to build images

Examples:
    # Run UAT with defaults
    $0

    # Run UAT with build
    $0 --build

    # Run UAT without cleanup (for debugging)
    $0 --no-cleanup

    # Run UAT with custom worktree
    $0 --worktree MyAgents-staging

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -b|--build)
            BUILD="true"
            shift
            ;;
        -nc|--no-cleanup)
            CLEANUP="false"
            shift
            ;;
        -w|--worktree)
            WORKTREE_NAME="$2"
            shift 2
            ;;
        -k|--key-path)
            GCP_SA_KEY_PATH="$2"
            shift 2
            ;;
        -r|--results-dir)
            UAT_RESULTS_DIR="$2"
            shift 2
            ;;
        *)
            print_message "$RED" "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Verify we're in the correct directory
if [ ! -f "docker-compose.uat.yml" ]; then
    print_message "$RED" "Error: docker-compose.uat.yml not found"
    print_message "$YELLOW" "Please run this script from /home/code/myagents directory"
    exit 1
fi

# Create results directory
mkdir -p "$UAT_RESULTS_DIR"

# Print configuration
print_message "$BLUE" "=== UAT Test Configuration ==="
echo "Worktree: $WORKTREE_NAME"
echo "GCP SA Key: $GCP_SA_KEY_PATH"
echo "Results Dir: $UAT_RESULTS_DIR"
echo "Build Images: $BUILD"
echo "Cleanup After: $CLEANUP"
echo ""

# Verify GCP service account exists
if [ ! -f "$GCP_SA_KEY_PATH" ]; then
    print_message "$RED" "Error: GCP service account key not found at: $GCP_SA_KEY_PATH"
    exit 1
fi

# Export environment variables for docker-compose
export WORKTREE_NAME
export GCP_SA_KEY_PATH
export UAT_RESULTS_DIR

# Build docker-compose command
COMPOSE_CMD="docker-compose -f docker-compose.uat.yml"
UP_ARGS="up --exit-code-from test --abort-on-container-exit"

if [ "$BUILD" = "true" ]; then
    UP_ARGS="$UP_ARGS --build"
fi

# Cleanup function
cleanup() {
    if [ "$CLEANUP" = "true" ]; then
        print_message "$YELLOW" "\n=== Cleaning up containers and volumes ==="
        $COMPOSE_CMD down -v || true
    else
        print_message "$YELLOW" "\n=== Skipping cleanup (--no-cleanup specified) ==="
        print_message "$BLUE" "To cleanup manually, run:"
        echo "  docker-compose -f docker-compose.uat.yml down -v"
    fi
}

# Set trap for cleanup
trap cleanup EXIT

# Run UAT tests
print_message "$GREEN" "=== Starting UAT Test Execution ==="
print_message "$BLUE" "Running: $COMPOSE_CMD $UP_ARGS"
echo ""

# Run tests and capture exit code
set +e
$COMPOSE_CMD $UP_ARGS
TEST_EXIT_CODE=$?
set -e

# Report results
echo ""
print_message "$BLUE" "=== UAT Test Results ==="

if [ $TEST_EXIT_CODE -eq 0 ]; then
    print_message "$GREEN" "SUCCESS: All UAT tests passed!"
    print_message "$BLUE" "Test results available in: $UAT_RESULTS_DIR"
else
    print_message "$RED" "FAILURE: UAT tests failed with exit code $TEST_EXIT_CODE"
    print_message "$YELLOW" "Check test results in: $UAT_RESULTS_DIR"
    print_message "$BLUE" "To debug, run with --no-cleanup and inspect containers"
fi

# List result files
if [ -d "$UAT_RESULTS_DIR" ] && [ "$(ls -A $UAT_RESULTS_DIR)" ]; then
    print_message "$BLUE" "\nGenerated artifacts:"
    ls -lh "$UAT_RESULTS_DIR"
fi

exit $TEST_EXIT_CODE
