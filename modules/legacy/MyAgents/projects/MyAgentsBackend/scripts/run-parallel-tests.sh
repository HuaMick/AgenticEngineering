#!/bin/bash
# Parallel Test Execution Script
# Purpose: Execute 6 test packages in parallel using Docker Compose
# Features: Build once, parallel execution, result aggregation, fail-fast on errors
#
# Usage: ./scripts/run-parallel-tests.sh
# Exit Codes:
#   0 - All tests passed
#   1 - One or more test packages failed
#   2 - Docker/infrastructure error

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test service names
TEST_SERVICES=(
  "test-cli-unification"
  "test-builder-agent"
  "test-infrastructure-workflow"
  "test-packaging"
  "test-integration-file-ops"
)

# Result files
RESULT_FILES=(
  "cli_unification.xml"
  "builder_agent.xml"
  "infrastructure_workflow.xml"
  "packaging.xml"
  "integration_file_ops.xml"
)

# Timeouts (in seconds) - 15 minutes per container
CONTAINER_TIMEOUT=900

# Logging functions
log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

# Cleanup function
cleanup() {
  log_info "Cleaning up containers and volumes..."
  docker-compose -f docker-compose.test.yml down -v 2>/dev/null || true
  log_info "Cleanup complete"
}

# Set up trap for cleanup on exit
trap cleanup EXIT

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

log_info "Starting parallel test execution"
log_info "Project root: $PROJECT_ROOT"

# Clean up any previous runs
log_info "Cleaning up previous test runs..."
cleanup

# Create results directory on host
mkdir -p "$PROJECT_ROOT/test-results"

# Build the test image once
log_info "Building test image (this may take a few minutes)..."
if ! docker-compose -f docker-compose.test.yml build --no-cache 2>&1 | tee build.log; then
  log_error "Failed to build test image"
  cat build.log
  exit 2
fi
log_success "Test image built successfully"

# Start all test containers in parallel
log_info "Starting test containers in parallel..."
docker-compose -f docker-compose.test.yml up -d 2>&1 | tee test-execution.log

# Wait for all containers to finish (with timeout)
log_info "Waiting for all test containers to complete (timeout: ${CONTAINER_TIMEOUT}s)..."
START_TIME=$(date +%s)
ALL_FINISHED=false

while [ $ALL_FINISHED = false ]; do
  CURRENT_TIME=$(date +%s)
  ELAPSED=$((CURRENT_TIME - START_TIME))

  if [ $ELAPSED -gt $CONTAINER_TIMEOUT ]; then
    log_error "Test execution timeout exceeded (${CONTAINER_TIMEOUT}s)"
    docker-compose -f docker-compose.test.yml logs
    exit 2
  fi

  # Check if all containers have stopped
  RUNNING_COUNT=$(docker-compose -f docker-compose.test.yml ps -q 2>/dev/null | xargs -r docker inspect -f '{{.State.Running}}' 2>/dev/null | grep -c true || true)
  if [ "$RUNNING_COUNT" -eq 0 ]; then
    ALL_FINISHED=true
    log_success "All test containers completed"
  else
    log_info "Waiting... ($RUNNING_COUNT containers still running)"
    sleep 10
  fi
done

# Copy results from Docker volume to host
log_info "Copying test results from Docker volume..."
# Docker Compose prefixes volume names with project name (directory name)
PROJECT_NAME=$(basename "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g')
VOLUME_NAME="${PROJECT_NAME}_test-results"
TEMP_CONTAINER=$(docker create -v "$VOLUME_NAME":/test/results alpine)

# Debug: List files in volume
log_info "Listing files in volume:"
docker start "$TEMP_CONTAINER"
docker exec "$TEMP_CONTAINER" ls -la /test/results || echo "Failed to list volume"

docker cp "$TEMP_CONTAINER:/test/results/." "$PROJECT_ROOT/test-results/" 2>/dev/null || true
docker rm -f "$TEMP_CONTAINER" >/dev/null 2>&1 || true

# Aggregate and analyze results
log_info "Analyzing test results..."
TOTAL_TESTS=0
TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0
EXIT_CODE=0

echo ""
echo "=========================================="
echo "        TEST RESULTS SUMMARY"
echo "=========================================="
echo ""

for i in "${!TEST_SERVICES[@]}"; do
  SERVICE="${TEST_SERVICES[$i]}"
  RESULT_FILE="$PROJECT_ROOT/test-results/${RESULT_FILES[$i]}"

  echo "Package: ${SERVICE#test-}"
  echo "----------------------------------------"

  if [ ! -f "$RESULT_FILE" ]; then
    log_error "Result file not found: ${RESULT_FILES[$i]}"
    echo "  Status: MISSING RESULTS"
    EXIT_CODE=1
    echo ""
    continue
  fi

  # Parse JUnit XML for test counts
  # Extract tests, failures, errors, skipped attributes
  if command -v xmllint >/dev/null 2>&1; then
    TESTS=$(xmllint --xpath "string(//testsuite/@tests)" "$RESULT_FILE" 2>/dev/null || echo "0")
    FAILURES=$(xmllint --xpath "string(//testsuite/@failures)" "$RESULT_FILE" 2>/dev/null || echo "0")
    ERRORS=$(xmllint --xpath "string(//testsuite/@errors)" "$RESULT_FILE" 2>/dev/null || echo "0")
    SKIPPED=$(xmllint --xpath "string(//testsuite/@skipped)" "$RESULT_FILE" 2>/dev/null || echo "0")
  else
    # Fallback: use grep and sed if xmllint is not available
    TESTS=$(grep -oP 'tests="\K[0-9]+' "$RESULT_FILE" | head -1 || echo "0")
    FAILURES=$(grep -oP 'failures="\K[0-9]+' "$RESULT_FILE" | head -1 || echo "0")
    ERRORS=$(grep -oP 'errors="\K[0-9]+' "$RESULT_FILE" | head -1 || echo "0")
    SKIPPED=$(grep -oP 'skipped="\K[0-9]+' "$RESULT_FILE" | head -1 || echo "0")
  fi

  # Default to 0 if empty
  TESTS=${TESTS:-0}
  FAILURES=${FAILURES:-0}
  ERRORS=${ERRORS:-0}
  SKIPPED=${SKIPPED:-0}

  PASSED=$((TESTS - FAILURES - ERRORS - SKIPPED))

  echo "  Total Tests: $TESTS"
  echo "  Passed: $PASSED"
  echo "  Failed: $FAILURES"
  echo "  Errors: $ERRORS"
  echo "  Skipped: $SKIPPED"

  if [ "$FAILURES" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
    echo -e "  Status: ${RED}FAILED${NC}"
    EXIT_CODE=1
  else
    echo -e "  Status: ${GREEN}PASSED${NC}"
  fi

  # Accumulate totals
  TOTAL_TESTS=$((TOTAL_TESTS + TESTS))
  TOTAL_PASSED=$((TOTAL_PASSED + PASSED))
  TOTAL_FAILED=$((TOTAL_FAILED + FAILURES))
  TOTAL_ERRORS=$((TOTAL_ERRORS + ERRORS))
  TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIPPED))

  echo ""
done

echo "=========================================="
echo "         OVERALL SUMMARY"
echo "=========================================="
echo "Total Tests Run: $TOTAL_TESTS"
echo "Total Passed: $TOTAL_PASSED"
echo "Total Failed: $TOTAL_FAILED"
echo "Total Errors: $TOTAL_ERRORS"
echo "Total Skipped: $TOTAL_SKIPPED"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
  log_success "All test packages passed!"
  echo -e "${GREEN}✓ SUCCESS${NC}"
else
  log_error "One or more test packages failed"
  echo -e "${RED}✗ FAILURE${NC}"
  
  # Debug: Show logs on failure
  log_info "Dumping container logs due to failure:"
  docker-compose -f docker-compose.test.yml logs
fi

echo ""
echo "Test results available in: $PROJECT_ROOT/test-results/"
echo "Test execution log: $PROJECT_ROOT/test-execution.log"
echo "Build log: $PROJECT_ROOT/build.log"
echo ""

# Show container exit codes for debugging
log_info "Container exit codes:"
for SERVICE in "${TEST_SERVICES[@]}"; do
  EXIT_STATUS=$(docker-compose -f docker-compose.test.yml ps -q "$SERVICE" 2>/dev/null | xargs docker inspect -f '{{.State.ExitCode}}' 2>/dev/null || echo "N/A")
  echo "  $SERVICE: $EXIT_STATUS"
done

exit $EXIT_CODE
