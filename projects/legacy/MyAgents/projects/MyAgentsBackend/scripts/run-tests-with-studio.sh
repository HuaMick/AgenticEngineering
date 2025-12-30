#!/bin/bash
set -e

echo "========================================="
echo "MyAgents Test Suite with Studio"
echo "========================================="
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

# Check if Studio is already running
echo "Checking Studio status..."
STUDIO_STATUS=$(myagents studio status 2>&1 || true)

if echo "$STUDIO_STATUS" | grep -q "RUNNING"; then
    echo "✓ Studio is already running"
    STUDIO_STARTED=false
else
    echo "Starting Studio service..."
    myagents studio start
    STUDIO_STARTED=true

    # Wait for Studio to be ready
    echo "Waiting for Studio to be ready..."
    sleep 5

    # Verify Studio is running
    MAX_ATTEMPTS=12
    ATTEMPT=0
    while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        if myagents studio status | grep -q "RUNNING"; then
            echo "✓ Studio is ready"
            break
        fi
        ATTEMPT=$((ATTEMPT + 1))
        echo "  Waiting... ($ATTEMPT/$MAX_ATTEMPTS)"
        sleep 5
    done

    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo "✗ Studio failed to start"
        exit 1
    fi
fi

# Run tests
echo ""
echo "Running test suite..."
echo "========================================="

# Run pytest with coverage
.venv/bin/pytest -v "$@"
TEST_EXIT_CODE=$?

# Cleanup: Stop Studio if we started it
if [ "$STUDIO_STARTED" = true ]; then
    echo ""
    echo "Stopping Studio service..."
    myagents studio stop
fi

# Report results
echo ""
echo "========================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✓ All tests passed"
else
    echo "✗ Some tests failed (exit code: $TEST_EXIT_CODE)"
fi
echo "========================================="

exit $TEST_EXIT_CODE
