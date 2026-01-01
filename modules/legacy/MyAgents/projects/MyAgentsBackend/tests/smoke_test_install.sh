#!/bin/bash
# =============================================================================
# MyAgents Installation Smoke Test
# =============================================================================
# PROC-001: Script that tests from clean install
#
# This script tests the complete installation and setup workflow:
# 1. Remove ~/.config/myagents (clean state)
# 2. pip install -e . (reinstall package)
# 3. Run myagents setup
# 4. Verify all config files created
# 5. Verify referenced files exist
# 6. Verify commands work
#
# Usage:
#   ./tests/smoke_test_install.sh
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
# =============================================================================

set -e  # Exit on first error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0

# Test helper functions
pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((PASSED++))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

info() {
    echo -e "  INFO: $1"
}

section() {
    echo ""
    echo "=============================================="
    echo "$1"
    echo "=============================================="
}

# =============================================================================
# Test Steps
# =============================================================================

section "Step 1: Clean State (Remove ~/.config/myagents)"

CONFIG_DIR="$HOME/.config/myagents"
BACKUP_DIR="$HOME/.config/myagents_backup_$$"

# Backup existing config if it exists
if [ -d "$CONFIG_DIR" ]; then
    info "Backing up existing config to $BACKUP_DIR"
    mv "$CONFIG_DIR" "$BACKUP_DIR"
fi

# Verify clean state
if [ ! -d "$CONFIG_DIR" ]; then
    pass "Config directory removed"
else
    fail "Config directory still exists"
fi

# =============================================================================

section "Step 2: Verify Package Installation"

# Check if myagents is installed
if command -v myagents &> /dev/null; then
    VERSION=$(myagents --version 2>&1 || echo "unknown")
    pass "myagents CLI is installed: $VERSION"
else
    fail "myagents CLI not found"
    exit 1
fi

# =============================================================================

section "Step 3: Run myagents setup"

if myagents setup 2>&1; then
    pass "myagents setup completed"
else
    fail "myagents setup failed"
fi

# =============================================================================

section "Step 4: Verify Config Files Created"

# Check config.yml
if [ -f "$CONFIG_DIR/config.yml" ]; then
    pass "config.yml exists"
else
    fail "config.yml not created"
fi

# Check langgraph.json
if [ -f "$CONFIG_DIR/langgraph.json" ]; then
    pass "langgraph.json exists"
else
    fail "langgraph.json not created"
fi

# =============================================================================

section "Step 5: Verify langgraph.json References Existing Files"

if [ -f "$CONFIG_DIR/langgraph.json" ]; then
    # Parse graphs from langgraph.json and verify each file exists
    GRAPHS=$(python3 -c "
import json
with open('$CONFIG_DIR/langgraph.json') as f:
    data = json.load(f)
for name, path in data.get('graphs', {}).items():
    file_path = path.split(':')[0]
    print(f'{name}:{file_path}')
" 2>/dev/null)

    if [ -z "$GRAPHS" ]; then
        warn "No graphs found in langgraph.json"
    else
        while IFS=: read -r graph_name file_path; do
            if [ -f "$file_path" ]; then
                pass "Graph '$graph_name' references existing file: $file_path"
            else
                fail "Graph '$graph_name' references missing file: $file_path"
            fi
        done <<< "$GRAPHS"
    fi
else
    warn "Skipping file verification (langgraph.json not found)"
fi

# =============================================================================

section "Step 6: Verify Commands Work"

# Test --version
if myagents --version &> /dev/null; then
    pass "--version works"
else
    fail "--version failed"
fi

# Test --help
if myagents --help &> /dev/null; then
    pass "--help works"
else
    fail "--help failed"
fi

# Test chat --help
if myagents chat --help &> /dev/null; then
    pass "chat --help works"
else
    fail "chat --help failed"
fi

# Test config show
if myagents config show &> /dev/null; then
    pass "config show works"
else
    fail "config show failed"
fi

# Test preferences list
if myagents preferences list &> /dev/null; then
    pass "preferences list works"
else
    fail "preferences list failed"
fi

# =============================================================================

section "Cleanup"

# Restore backup if it existed
if [ -d "$BACKUP_DIR" ]; then
    info "Restoring original config from $BACKUP_DIR"
    rm -rf "$CONFIG_DIR"
    mv "$BACKUP_DIR" "$CONFIG_DIR"
    pass "Original config restored"
fi

# =============================================================================

section "Summary"

TOTAL=$((PASSED + FAILED))
echo ""
echo "Tests Run: $TOTAL"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All smoke tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some smoke tests failed!${NC}"
    exit 1
fi
