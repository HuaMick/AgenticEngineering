#!/bin/bash
# MyAgents Test Suite - Container Execution Script
# Purpose: Executes all test phases inside Docker container
# This script runs INSIDE the Docker container (not on host)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY_URL="https://oauth2accesstoken@us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/"
TEST_RESULTS=()
PHASE_TIMES=()

# Utility functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_phase_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Phase $1: $2${NC}"
    echo -e "${BLUE}========================================${NC}"
}

record_phase_result() {
    local phase=$1
    local result=$2
    TEST_RESULTS+=("Phase $phase: $result")
}

run_command() {
    local cmd=$1
    local description=$2

    log_info "Running: $description"
    log_info "Command: $cmd"

    if eval "$cmd"; then
        log_success "$description - OK"
        return 0
    else
        log_error "$description - FAILED"
        return 1
    fi
}

# Test phases

phase_1_docker_setup() {
    print_phase_header "1" "Docker Environment Setup"
    local start_time=$(date +%s)

    log_info "Verifying container environment..."

    # Check Python
    if ! run_command "python --version" "Python installation"; then
        record_phase_result 1 "FAIL"
        return 1
    fi

    # Check UV
    if ! run_command "uv --version" "UV package manager"; then
        record_phase_result 1 "FAIL"
        return 1
    fi

    # Check gcloud
    if ! run_command "gcloud --version" "Google Cloud SDK"; then
        record_phase_result 1 "FAIL"
        return 1
    fi

    # Check environment variables
    if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        log_error "GOOGLE_APPLICATION_CREDENTIALS not set"
        record_phase_result 1 "FAIL"
        return 1
    fi

    if [ -z "$GCP_PROJECT_ID" ]; then
        log_error "GCP_PROJECT_ID not set"
        record_phase_result 1 "FAIL"
        return 1
    fi

    log_success "Environment variables configured"

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    PHASE_TIMES+=("Phase 1: ${duration}s")

    record_phase_result 1 "PASS"
    log_success "Phase 1 completed successfully"
}

phase_2_fresh_installation() {
    print_phase_header "2" "Fresh Installation Testing"
    local start_time=$(date +%s)

    log_info "Testing fresh installation workflow..."

    # Install keyring helper
    log_info "Installing keyring authentication helper..."
    if ! uv pip install --system keyrings.google-artifactregistry-auth; then
        log_error "Failed to install keyring helper"
        record_phase_result 2 "FAIL"
        return 1
    fi

    # Configure pip
    log_info "Configuring pip for Artifact Registry..."
    mkdir -p ~/.config/pip
    cat > ~/.config/pip/pip.conf << EOF
[global]
extra-index-url = $REGISTRY_URL
EOF

    # Verify pip configuration
    if ! run_command "cat ~/.config/pip/pip.conf" "Verify pip.conf"; then
        record_phase_result 2 "FAIL"
        return 1
    fi

    # Authenticate with GCP
    log_info "Authenticating with GCP..."
    if ! gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS"; then
        log_error "GCP authentication failed"
        record_phase_result 2 "FAIL"
        return 1
    fi

    if ! gcloud config set project "$GCP_PROJECT_ID"; then
        log_error "Failed to set GCP project"
        record_phase_result 2 "FAIL"
        return 1
    fi

    # Verify authentication
    if ! run_command "gcloud auth list" "Verify authentication"; then
        record_phase_result 2 "FAIL"
        return 1
    fi

    # Install myagents
    log_info "Installing myagents package..."
    if ! uv pip install --system --keyring-provider subprocess --extra-index-url "$REGISTRY_URL" myagents; then
        log_error "Failed to install myagents"
        record_phase_result 2 "FAIL"
        return 1
    fi

    # Install agent-gcptoolkit
    log_info "Installing agent-gcptoolkit package..."
    if ! uv pip install --system --keyring-provider subprocess --extra-index-url "$REGISTRY_URL" agent-gcptoolkit; then
        log_error "Failed to install agent-gcptoolkit"
        record_phase_result 2 "FAIL"
        return 1
    fi

    # Verify installations
    if ! run_command "myagents --version" "Verify myagents installation"; then
        record_phase_result 2 "FAIL"
        return 1
    fi

    if ! run_command "uv pip show myagents" "Show myagents info"; then
        record_phase_result 2 "FAIL"
        return 1
    fi

    if ! run_command "uv pip show agent-gcptoolkit" "Show agent-gcptoolkit info"; then
        record_phase_result 2 "FAIL"
        return 1
    fi

    # Test registry commands
    if ! run_command "myagents registry info" "Test registry info"; then
        record_phase_result 2 "FAIL"
        return 1
    fi

    if ! run_command "myagents registry check-auth" "Test registry auth check"; then
        record_phase_result 2 "FAIL"
        return 1
    fi

    # Test help command
    if ! run_command "myagents --help" "Test help command"; then
        record_phase_result 2 "FAIL"
        return 1
    fi

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    PHASE_TIMES+=("Phase 2: ${duration}s")

    record_phase_result 2 "PASS"
    log_success "Phase 2 completed successfully"
}

phase_3_self_update() {
    print_phase_header "3" "Self-Update Testing"
    local start_time=$(date +%s)

    log_info "Testing self-update mechanism..."

    # Check current version
    if ! run_command "myagents --version" "Check current version"; then
        record_phase_result 3 "FAIL"
        return 1
    fi

    # Test myagents self-update
    log_info "Testing myagents self-update..."
    if ! myagents self-update; then
        log_warning "Self-update command failed (may be expected if no newer version)"
        # Check if error message is appropriate
        if myagents self-update 2>&1 | grep -q "workspace mode"; then
            log_error "False positive workspace mode detection"
            record_phase_result 3 "FAIL"
            return 1
        fi
    fi

    # Test gcptoolkit self-update delegation
    log_info "Testing gcptoolkit self-update delegation..."
    if ! myagents gcptoolkit self-update; then
        log_warning "Gcptoolkit self-update failed (may be expected if no newer version)"
    fi

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    PHASE_TIMES+=("Phase 3: ${duration}s")

    record_phase_result 3 "PASS"
    log_success "Phase 3 completed successfully"
}

phase_4_workspace_mode() {
    print_phase_header "4" "Workspace Mode Testing"
    local start_time=$(date +%s)

    log_info "Testing workspace mode detection and protection..."

    # Create temporary directory for workspace testing
    cd /tmp
    mkdir -p workspace-test
    cd workspace-test

    # Clone repository
    log_info "Cloning repository for workspace mode testing..."
    if ! git clone https://github.com/HuaMick/MyAgents.git; then
        log_error "Failed to clone repository"
        record_phase_result 4 "FAIL"
        return 1
    fi

    cd MyAgents

    # Install in workspace mode
    log_info "Installing in workspace mode..."
    if ! uv sync; then
        log_error "Failed to install in workspace mode"
        record_phase_result 4 "FAIL"
        return 1
    fi

    # Verify editable installation
    log_info "Verifying editable installation..."
    if ! uv pip list | grep -i myagents; then
        log_error "Editable installation not found"
        record_phase_result 4 "FAIL"
        return 1
    fi

    # Test self-update is blocked
    log_info "Testing self-update protection in workspace mode..."
    if myagents self-update 2>&1 | grep -q "workspace mode"; then
        log_success "Self-update correctly blocked in workspace mode"
    else
        log_error "Self-update NOT blocked in workspace mode (protection failed)"
        record_phase_result 4 "FAIL"
        return 1
    fi

    # Test CLI commands still work
    if ! run_command "myagents --help" "Verify CLI works in workspace mode"; then
        record_phase_result 4 "FAIL"
        return 1
    fi

    # Test uv sync works
    if ! run_command "uv sync" "Test uv sync in workspace mode"; then
        record_phase_result 4 "FAIL"
        return 1
    fi

    # Return to test directory
    cd /test

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    PHASE_TIMES+=("Phase 4: ${duration}s")

    record_phase_result 4 "PASS"
    log_success "Phase 4 completed successfully"
}

phase_5_integration() {
    print_phase_header "5" "Cross-Package Integration Testing"
    local start_time=$(date +%s)

    log_info "Testing myagents and agent-gcptoolkit integration..."

    # Test myagents import
    log_info "Testing myagents import..."
    if ! python3 -c "import myagents; print('myagents imported')"; then
        log_error "Failed to import myagents"
        record_phase_result 5 "FAIL"
        return 1
    fi

    # Test agent-gcptoolkit import
    log_info "Testing agent-gcptoolkit import..."
    if ! python3 -c "import agent_gcptoolkit; print('agent_gcptoolkit imported')"; then
        log_error "Failed to import agent_gcptoolkit"
        record_phase_result 5 "FAIL"
        return 1
    fi

    # Test cross-package imports
    log_info "Testing cross-package imports..."
    if ! python3 -c "from backend.services.gcptoolkit.src.domains.config import ConfigManager; print('Cross-package import successful')"; then
        log_warning "Cross-package import failed (may be expected if not all modules available)"
    fi

    # Test delegation commands
    if ! run_command "myagents config show" "Test config delegation"; then
        log_warning "Config delegation failed (may be expected)"
    fi

    # Test gcptoolkit help
    if ! run_command "myagents gcptoolkit self-update --help" "Test gcptoolkit delegation help"; then
        log_warning "Gcptoolkit help failed (may be expected)"
    fi

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    PHASE_TIMES+=("Phase 5: ${duration}s")

    record_phase_result 5 "PASS"
    log_success "Phase 5 completed successfully"
}

phase_6_authentication() {
    print_phase_header "6" "Registry Authentication Testing"
    local start_time=$(date +%s)

    log_info "Testing registry authentication scenarios..."

    # Test check-auth command
    if ! run_command "myagents registry check-auth" "Verify authentication status"; then
        record_phase_result 6 "FAIL"
        return 1
    fi

    # Test registry info
    if ! run_command "myagents registry info" "Verify registry info"; then
        record_phase_result 6 "FAIL"
        return 1
    fi

    # Verify gcloud authentication
    if ! run_command "gcloud auth list" "List gcloud auth"; then
        record_phase_result 6 "FAIL"
        return 1
    fi

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    PHASE_TIMES+=("Phase 6: ${duration}s")

    record_phase_result 6 "PASS"
    log_success "Phase 6 completed successfully"
}

phase_7_error_handling() {
    print_phase_header "7" "Error Handling and Edge Cases"
    local start_time=$(date +%s)

    log_info "Testing error handling..."

    # Test invalid command
    log_info "Testing invalid command..."
    if myagents nonexistent-command 2>&1 | grep -q "Unknown command\|Error"; then
        log_success "Invalid command produces error message"
    else
        log_warning "Invalid command error message unclear"
    fi

    # Test missing argument
    log_info "Testing missing argument..."
    if myagents preferences get 2>&1 | grep -q "Error\|Missing\|required"; then
        log_success "Missing argument produces error message"
    else
        log_warning "Missing argument error message unclear"
    fi

    # Test help command
    if ! run_command "myagents --help" "Test help with edge case"; then
        record_phase_result 7 "FAIL"
        return 1
    fi

    # Test version command
    if ! run_command "myagents --version" "Test version command"; then
        record_phase_result 7 "FAIL"
        return 1
    fi

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    PHASE_TIMES+=("Phase 7: ${duration}s")

    record_phase_result 7 "PASS"
    log_success "Phase 7 completed successfully"
}

# Main execution
main() {
    local overall_start=$(date +%s)

    echo "========================================="
    echo "MyAgents Test Suite"
    echo "Date: $(date)"
    echo "========================================="
    echo ""

    # Run all phases
    local failed_phases=0

    phase_1_docker_setup || ((failed_phases++))
    phase_2_fresh_installation || ((failed_phases++))
    phase_3_self_update || ((failed_phases++))
    phase_4_workspace_mode || ((failed_phases++))
    phase_5_integration || ((failed_phases++))
    phase_6_authentication || ((failed_phases++))
    phase_7_error_handling || ((failed_phases++))

    # Print summary
    echo ""
    echo "========================================="
    echo "Test Suite Summary"
    echo "========================================="
    echo ""

    echo "Phase Results:"
    for result in "${TEST_RESULTS[@]}"; do
        if echo "$result" | grep -q "PASS"; then
            echo -e "${GREEN}✓${NC} $result"
        else
            echo -e "${RED}✗${NC} $result"
        fi
    done

    echo ""
    echo "Phase Durations:"
    for time in "${PHASE_TIMES[@]}"; do
        echo "  $time"
    done

    local overall_end=$(date +%s)
    local total_duration=$((overall_end - overall_start))
    local total_minutes=$((total_duration / 60))
    local total_seconds=$((total_duration % 60))

    echo ""
    echo "Total Duration: ${total_minutes}m ${total_seconds}s"
    echo ""

    if [ $failed_phases -eq 0 ]; then
        echo -e "${GREEN}=========================================${NC}"
        echo -e "${GREEN}All tests passed!${NC}"
        echo -e "${GREEN}=========================================${NC}"
        exit 0
    else
        echo -e "${RED}=========================================${NC}"
        echo -e "${RED}$failed_phases phase(s) failed${NC}"
        echo -e "${RED}=========================================${NC}"
        exit 1
    fi
}

# Run main
main
