# End-to-End (E2E) Testing Guide

This directory contains end-to-end tests for build/deploy cycles and complete packaging workflows.

## Purpose

E2E tests validate complete user workflows from start to finish, testing the full lifecycle:
- Building packages from source
- Installing/updating packages
- Running CLI commands after deployment
- Multi-package coordination
- Error recovery scenarios

These tests ensure that the entire system works together correctly, beyond what unit or workflow-specific tests can verify.

## Test Files

### Build/Deploy Cycle Tests

- `test_myagents_build_deploy_e2e.py` - Complete MyAgents and GCPToolkit build/deploy workflows
  - Complete rebuild workflows (build + install in one command)
  - Build to install progression (separate steps)
  - Update workflows (incremental updates)
  - Multi-package coordination (GCPToolkit + MyAgents)
  - Worktree isolation and switching
  - Error recovery after failed builds/updates
  - Package version consistency
  - Preference persistence across updates

### CLI Command Tests

- `test_gcptoolkit_cli_e2e.py` - GCPToolkit CLI end-to-end tests
  - Build command (`gcptoolkit build`)
  - Update command (`gcptoolkit update`)
  - Rebuild command (`gcptoolkit rebuild`)
  - Version command (`gcptoolkit --version`)
  - Secret storage and environment integration

- `test_myagents_cli_e2e.py` - MyAgents CLI end-to-end tests
  - Update command (`myagents update`)
  - Rebuild command (`myagents rebuild`)
  - Version command (`myagents --version`)
  - Preferences management across updates
  - Studio integration

### Installation and Build Tests

- `test_installation_script_e2e.py` - Installation script validation
  - Fresh installation workflows
  - Idempotency (can run multiple times safely)
  - Error handling and recovery
  - Documentation completeness

- `test_makefile_e2e.py` - Makefile target validation
  - Target ordering and dependencies
  - Complete make-based workflows
  - Error propagation
  - Integration between targets

- `test_self_update_e2e.py` - Self-update mechanism tests
  - Package update workflows
  - Dependency coordination
  - Version consistency

## When to Add Tests Here vs Workflow-Specific Packages

### Add tests to e2e/ when:

1. Testing complete build/deploy/update cycles
2. Testing CLI commands AFTER deployment (installed state)
3. Testing multi-package coordination (GCPToolkit + MyAgents)
4. Testing error recovery across multiple operations
5. Testing state persistence across package updates
6. Validating installation scripts or Makefile workflows

### Add tests to workflow-specific packages when:

1. Testing a single workflow's internal logic
2. Testing API/function calls (not CLI commands)
3. Testing domain-specific behavior (echo, secrets, shell ops)
4. Unit testing individual components
5. Testing workflow configuration or setup

**Rule of thumb:** If the test requires an installed package or tests the entire lifecycle from source to deployed CLI, it belongs in e2e/. If it tests workflow logic or domain behavior, it belongs in the workflow-specific package.

## Running Tests

### Run All E2E Tests
```bash
cd /home/code/myagents/MyAgents-test-refactor
pytest tests/workflows/e2e/ -v -m e2e
```

### Run Specific Test Modules

**Build/Deploy Cycles:**
```bash
pytest tests/workflows/e2e/test_myagents_build_deploy_e2e.py -v
```

**GCPToolkit CLI:**
```bash
pytest tests/workflows/e2e/test_gcptoolkit_cli_e2e.py -v
```

**MyAgents CLI:**
```bash
pytest tests/workflows/e2e/test_myagents_cli_e2e.py -v
```

**Installation Script:**
```bash
pytest tests/workflows/e2e/test_installation_script_e2e.py -v
```

**Makefile:**
```bash
pytest tests/workflows/e2e/test_makefile_e2e.py -v
```

**Self-Update:**
```bash
pytest tests/workflows/e2e/test_self_update_e2e.py -v
```

### Run Specific Test Classes

```bash
# Complete rebuild workflow
pytest tests/workflows/e2e/test_myagents_build_deploy_e2e.py::TestCompleteRebuildWorkflow -v

# Multi-package coordination
pytest tests/workflows/e2e/test_myagents_build_deploy_e2e.py::TestMultiPackageCoordination -v

# GCPToolkit build tests
pytest tests/workflows/e2e/test_gcptoolkit_cli_e2e.py::TestGCPToolkitBuild -v

# MyAgents update tests
pytest tests/workflows/e2e/test_myagents_cli_e2e.py::TestMyAgentsUpdate -v
```

### Quick Validation (Fast Tests Only)

```bash
pytest tests/workflows/e2e/ -k "validation or help or syntax or version" -v
```

### Skip Long-Running Tests

```bash
pytest tests/workflows/e2e/ -k "not make_based and not update_test" -v
```

## Test Environment Requirements

### General Requirements

- MyAgents CLI must be installed (current version, not old)
- UV package manager available
- Git worktree properly configured
- Python 3.11+ environment

### For GCPToolkit Tests

- Agent-GCPtoolkit repository available (typically at `/home/code/myagents/Agent-GCPtoolkit`)
- GCPToolkit CLI installed and in PATH
- Build environment should NOT have GCP registry authentication configured (to prevent interactive prompts)

### For Build Tests

- Build artifacts directory accessible
- No GCP registry configured in pip.conf (prevents authentication prompts during builds)
- `PIP_NO_INPUT=1` environment variable set for non-interactive builds

### For Workspace Tests

- Worktree must be listed in parent workspace's pyproject.toml
- UV workspace properly configured
- Multiple worktrees may be required for isolation tests

## Common Test Patterns

### GCPToolkit CLI Testing Pattern

1. Version Check: Verify CLI is available and returns version
2. Build Command: Create build artifacts in build-artifacts/dist
3. Update Command: Install built package to environment
4. Rebuild Command: Combined build + update
5. Verify Functionality: Run CLI commands after installation

### MyAgents CLI Testing Pattern

1. Version/Help Check: Verify CLI is available
2. Update Command: Install/update package in place
3. Rebuild Command: Full build + install cycle
4. Verify Functionality: Test specific commands (preferences, studio, etc.)
5. Verify Persistence: Ensure user data survives updates

### Build/Deploy Cycle Pattern

1. Clean State: Start from known state
2. Build: Create artifacts from source
3. Install: Deploy artifacts to environment
4. Verify: Run CLI commands and check functionality
5. Update: Incremental update
6. Verify Again: Ensure functionality preserved
7. Recovery: Test error scenarios and recovery

## Troubleshooting

### Tests Fail with "ModuleNotFoundError"

```bash
cd /home/code/myagents/MyAgents-test-refactor
uv sync
source .venv/bin/activate
```

### Tests Skip Due to Missing GCPToolkit

The Agent-GCPtoolkit repository must be available. Clone it to:
- `/home/code/myagents/Agent-GCPtoolkit` (recommended)
- Or install gcptoolkit package to system

### Tests Skip Due to GCP Registry Configuration

If you have GCP registry configured in pip.conf, some build tests will skip to avoid interactive authentication prompts. This is expected behavior.

### Timeouts

```bash
# Run without timeout-prone tests
pytest tests/workflows/e2e/ -k "not make_based and not update_test" -v

# Increase timeout for specific tests (in test code)
```

### Detailed Output

```bash
# Verbose with full traceback
pytest tests/workflows/e2e/ -vv --tb=long

# Show print statements
pytest tests/workflows/e2e/ -v -s
```

### Workspace Not Configured

If tests skip with "not a workspace member" message:
1. Check parent directory has pyproject.toml with workspace configuration
2. Verify current worktree is listed in workspace members
3. Run `uv sync` to update workspace

## Test Markers

All tests in this directory use the `@pytest.mark.e2e` marker:

```python
# At module level
pytestmark = pytest.mark.e2e
```

Run only e2e tests:
```bash
pytest -m e2e -v
```

Exclude e2e tests:
```bash
pytest -m "not e2e" -v
```

## Notes

- E2E tests may modify installed packages (that's intentional)
- Some tests require external repositories (Agent-GCPtoolkit)
- Tests may skip if prerequisites are not met
- Build artifacts may need cleanup between test runs
- Tests use subprocess to run actual CLI commands (not Python API calls)
- Tests validate real-world user workflows, not just code coverage
