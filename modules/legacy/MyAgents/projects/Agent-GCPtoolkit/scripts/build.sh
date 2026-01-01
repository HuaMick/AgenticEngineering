#!/bin/bash
set -e

PROJECT_ROOT="/home/code/myagents/Agent-GCPtoolkit"
BUILD_DIR="$PROJECT_ROOT/build-artifacts"

echo "=== Cleaning build-artifacts/ ==="
rm -rf "$BUILD_DIR/dist"/* "$BUILD_DIR/build"/* "$BUILD_DIR"/*.egg-info

echo "=== Building package with UV ==="
cd "$PROJECT_ROOT"
uv build --out-dir "$BUILD_DIR/dist"

echo "=== Build artifacts created ==="
ls -lh "$BUILD_DIR/dist/"

echo "=== Build complete ==="
echo "Wheel location: $BUILD_DIR/dist/"
