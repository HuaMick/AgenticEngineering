#!/bin/bash
set -e

PROJECT_ROOT="/home/code/myagents/Agent-GCPtoolkit"
BUILD_DIR="$PROJECT_ROOT/build-artifacts"

echo "=== Cleaning build-artifacts/ ==="
rm -rf "$BUILD_DIR/dist"/* "$BUILD_DIR/build"/* "$BUILD_DIR"/*.egg-info

echo "=== Cleaning __pycache__ ==="
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$PROJECT_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true

echo "=== Clean complete ==="
