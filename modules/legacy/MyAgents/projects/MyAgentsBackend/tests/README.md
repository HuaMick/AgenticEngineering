# Testing Guide

This document explains the workflow-based test structure and how to run, write, and maintain tests.

## Quick Start

```bash
# Run all tests with workflow health report
make test-all

# Run tests for specific workflows
make test-workflow-health-check
make test-workflow-studio
make test-workflow-preferences
make test-workflow-help
make test-workflow-cli-routing

# Run agent tests
make test-agent-chat
make test-agent-shell-operations

# Run cross-workflow tests
make test-e2e
```

## Test Structure

Tests are organized by workflow to match the application's architecture:

```
tests/
├── workflows/                             # Workflow-specific tests
│   ├── health_check/                      # Health check workflow tests (61 tests)
│   ├── studio/                            # Studio workflow tests (31 tests)
│   ├── preferences/                       # Preferences workflow tests (31 tests)
│   ├── help/                              # Help workflow tests (35 tests)
│   ├── cli_routing/                       # CLI routing workflow tests (30 tests)
│   ├── e2e/                               # End-to-end tests (80 tests)
│   ├── agent_chat/                        # Chat agent tests (1 test)
│   ├── agent_shell_operations/            # Shell operations agent tests (67 tests)
│   ├── infrastructure/                    # Cross-workflow CLI integration tests (16 tests)
│   ├── cli_unification/                   # CLI unification tests (23 tests)
│   └── secrets_workflow/                  # Secrets workflow (placeholder)
├── integration/                           # Legacy integration tests (150 tests)
│   ├── file_operations/                   # File operations integration tests
│   ├── git_operations/                    # Git operations integration tests
│   └── shell_operations/                  # Shell operations integration tests
├── manual/                                # Manual test scripts (no automated tests)
├── utils/
│   ├── __init__.py
│   └── health_reporter.py                 # Workflow health monitoring plugin
├── conftest.py                            # Shared pytest fixtures
└── pytest.ini                             # Pytest configuration

Current test count: 525 tests total
- Workflow tests (375 tests across 10 packages):
  - health_check: 61 tests
  - studio: 31 tests
  - preferences: 31 tests
  - help: 35 tests
  - cli_routing: 30 tests
  - e2e: 80 tests
  - agent_chat: 1 test
  - agent_shell_operations: 67 tests
  - infrastructure_cli: 16 tests
  - cli_unification: 23 tests
  - secrets_workflow: 0 tests (placeholder)
- Legacy integration tests (150 tests):
  - file_operations: Integration tests for file operations
  - git_operations: Integration tests for git operations
  - shell_operations: Integration tests for shell operations

Note: Test counts shown above are per-directory counts. Some tests may have multiple pytest
markers for categorization purposes, but each test is counted only once in its primary package.
```

## Naming Convention

Tests are organized using a consistent naming convention:

- **workflow_<name>**: For CLI/infrastructure workflow tests
  - `workflow_health_check` - Health check workflow
  - `workflow_studio` - Studio workflow
  - `workflow_preferences` - Preferences workflow
  - `workflow_help` - Help workflow
  - `workflow_cli_routing` - CLI routing workflow

- **agent_<capability>**: For agent workflow tests
  - `agent_chat` - Chat agent tests
  - `agent_shell_operations` - Shell operations agent tests

- **e2e**: For cross-workflow end-to-end tests
- **infrastructure_cli**: Cross-workflow CLI integration tests

## Test Organization

### Important: Workflow-Based vs Traditional Test Organization

This project uses **workflow-based test organization** instead of traditional unit/integration markers:

- **No unit marker usage**: The `unit` marker is defined in pytest.ini for future use, but currently no tests use it. Running `pytest -m "unit"` will find 0 tests (all deselected).
- **Use workflow markers instead**: Tests are organized by workflow (workflow_*, agent_*, e2e, infrastructure_cli, etc.) to match the application architecture.
- **Fast tests**: Use `make test-myagents-quick` for a quick test run, or `pytest -m "not costly"` to exclude expensive tests.
- **Full test suite**: Use `make test-all` to run all tests with workflow health reporting.

The workflow-based approach provides better alignment with the application's modular architecture and makes it easier to test specific features or components.

### Workflow Tests

Each workflow has its own package with dedicated tests:

1. **health_check** - CLI infrastructure validation and root detection (61 tests)
2. **studio** - LangGraph Studio lifecycle management (31 tests)
3. **preferences** - User preference management (31 tests)
4. **help** - CLI help and documentation (35 tests)
5. **cli_routing** - CLI command routing (30 tests)

### Agent Tests

Agent-specific functionality is tested in agent packages:

1. **agent_chat** - Chat agent tests (1 test)
2. **agent_shell_operations** - Shell operations agent tests (67 tests)

### Cross-Workflow Tests

1. **infrastructure** - Cross-workflow CLI integration tests (16 tests)
   - Located in `tests/workflows/infrastructure/`
   - Tests CLI integration across multiple workflows
   - Command routing and availability
   - Error handling

2. **e2e** - End-to-end tests (80 tests)
   - Located in `tests/workflows/e2e/`
   - Full workflow integration tests
   - Packaging and installation tests
   - CLI command execution tests
   - GCPToolkit CLI integration

3. **cli_unification** - CLI unification tests (23 tests)
   - Tests for unified CLI command structure

### CLI Test Organization

CLI testing is intentionally distributed across multiple specialized test files, each with distinct responsibilities. This separation prevents test file bloat while maintaining clear boundaries between different aspects of CLI functionality.

#### CLI Test File Boundaries

1. **test_cli_integration.py** (258 lines) - Command Availability Smoke Tests
   - Location: `tests/workflows/infrastructure/`
   - Purpose: Validates that CLI commands exist and are discoverable
   - Tests: "Does command X exist in the CLI?"
   - Scope: Surface-level command availability checks
   - Example tests: Command help output, version display, basic command registration

2. **test_unified_cli_e2e.py** (928 lines) - CLI Unification Tests
   - Location: `tests/workflows/cli_unification/`
   - Purpose: Tests unified CLI architecture and command delegation
   - Tests: "Does the unified CLI correctly delegate to subcommands?"
   - Scope: End-to-end unified CLI behavior, cross-workflow command coordination
   - Example tests: Unified help system, command namespace management, backward compatibility
   - Note: Large file size is intentional - organized by test class, well-structured

4. **test_myagents_cli_e2e.py** (389 lines) - Package Installation Tests
   - Location: `tests/workflows/e2e/`
   - Purpose: Validates package installation and update workflows
   - Tests: "Does install/update work correctly?"
   - Scope: Package lifecycle, CLI entrypoint installation, version management
   - Example tests: Package installation, CLI availability post-install, update workflows

5. **test_global_command_architecture_e2e.py** (749 lines) - Architecture Validation Tests
   - Location: `tests/workflows/health_check/`
   - Purpose: Cross-cutting architecture validation and consistency checks
   - Tests: "Does the overall command architecture maintain consistency?"
   - Scope: Global command patterns, architectural constraints, system-wide consistency
   - Example tests: Command naming conventions, help text consistency, error handling patterns
   - Note: Large file size is intentional - comprehensive architecture validation

#### Why Multiple CLI Test Files?

This separation provides several benefits:

1. **Clear Separation of Concerns**: Each file tests a distinct layer of the CLI stack
2. **Maintainability**: Changes to routing logic don't affect installation tests
3. **Test Isolation**: Failures in one area don't cascade across unrelated functionality
4. **Parallel Development**: Different developers can work on different CLI aspects
5. **Targeted Testing**: Run only the tests relevant to your changes

#### Large Test Files Are Intentional

Some test files exceed 600-900 lines. This is intentional and should not trigger refactoring:

- **Well-Organized**: Files are structured by test class with clear sections
- **Comprehensive Coverage**: Large files indicate thorough testing of complex systems
- **Logical Grouping**: Related tests belong together for context
- **Easy Navigation**: Test classes provide natural organization boundaries

Do not split large test files unless they violate single responsibility or become unmaintainable.

### Other Key Test Patterns

#### Single Source of Truth Tests

1. **test_preferences_workflow.py** (486 lines)
   - Location: `tests/workflows/preferences/`
   - Purpose: Single source of truth for preference management logic
   - All preference-related tests are consolidated here
   - Prevents fragmentation of preference testing logic

#### Complementary Test Separation

Shell operation tests are intentionally split between integration and workflow tests:

1. **tests/integration/shell_operations/** - Integration-level shell tests
   - Domain and tool-level integration
   - Shell command execution mechanics
   - Security constraints and validation

2. **tests/workflows/agent_shell_operations/** - Agent workflow tests
   - Agent-level shell operation workflows
   - Higher-level orchestration and behavior
   - Agent-specific shell capabilities

These are complementary, not redundant. Both test layers serve distinct purposes.

#### Intentional Placeholders

**tests/workflows/secrets_workflow/** is an intentional placeholder:
- Directory exists for structural consistency
- No tests currently defined (secrets logic tested elsewhere)
- Tests are integrated into relevant workflow test files
- Placeholder prevents confusion about missing test coverage

### Legacy Integration Tests

The `tests/integration/` directory contains legacy integration tests (150 tests) that predate the
workflow-based organization:

1. **file_operations** - File operation integration tests
   - Tests file reading, writing, and manipulation
   - Domain and tool-level integration tests

2. **git_operations** - Git operation integration tests
   - Tests git command execution and workflow
   - Domain and tool-level integration tests

3. **shell_operations** - Shell operation integration tests
   - Tests shell command execution
   - Security constraints and validation

These tests are maintained for backward compatibility but new tests should be added to the
appropriate workflow package in `tests/workflows/`.

## E2E Test Requirements

Some tests require a running LangGraph Studio service:

**Tests requiring Studio:**
- `tests/workflows/infrastructure/test_studio_workflow.py` - Studio lifecycle tests
- Some CLI integration tests that check Studio status

**Running without Studio:**
```bash
# Skip Studio-dependent tests
pytest -m "not studio" -v

# Run only unit tests
pytest tests/workflows/infrastructure/ -k "not studio" -v
```

**Running with Studio:**
```bash
# Start Studio first
myagents studio start

# Run all tests
pytest tests/workflows/infrastructure/ -v

# Stop Studio
myagents studio stop
```

## Expected Test Results

**Current Status:** 523 passed, 2 skipped (99.6% pass rate) across 525 total tests
- Workflow tests: 375 tests (all passing)
- Legacy integration tests: 150 tests (all passing)

All tests should pass in the current implementation. The 2 expected skips are documented below.

### Expected Skips

The following tests are expected to skip in CI/CD and isolated environments:

| Test | File | Reason | Marker |
|------|------|--------|--------|
| `test_multiple_worktrees_dont_conflict` | `test_integration_workflows_e2e.py` | Requires MyAgents-packaging-001 worktree | `requires_packaging_worktree` |
| `test_make_based_workflow` | `test_integration_workflows_e2e.py` | Requires packaging worktree | `requires_packaging_worktree` |

**Why these skip:**
- These are end-to-end integration tests that validate multi-worktree operations
- They require the `MyAgents-packaging-001` git worktree to be checked out
- They're designed for local development validation, not CI/CD

**Running locally with all tests:**
```bash
# Check out required worktrees
cd /home/code/myagents
git worktree add MyAgents-packaging-001 packaging-001

# Run all tests
uv run pytest -v
```

**Skipping packaging worktree tests in CI:**
```bash
uv run pytest -m "not requires_packaging_worktree" -v
```

### Detection Behavior

MyAgents uses simplified path detection with no fallbacks or auto-creation:

**Project Root Detection** (`detect_project_root()`):
- Walks up directory tree from current working directory
- Looks for `langgraph.json` file
- Stops at `/tmp` boundary to avoid test pollution
- No home directory fallback
- Error: "No langgraph.json found. Run from project directory or use 'myagents setup'."

**Config Path Detection** (`detect_config_path()`):
- Checks only `~/.config/myagents/config.yml`
- Home directory only, no project-level config
- Returns `None` if not found (no auto-creation)
- Users should run `myagents preferences` to create config

**LangGraph Path Detection** (`detect_langgraph_path()`):
- Checks only `~/.config/myagents/langgraph.json`
- No auto-creation of files or directories
- Returns `None` if not found
- Respects `MYAGENTS_TEST_ISOLATION` for test isolation

**Removed Functionality** (13 tests removed):
- No `required` parameter in `detect_project_root()`
- No `project_root` parameter in `detect_config_path()`
- No `allow_fallback` parameter in `detect_langgraph_path()`
- No home directory fallback for project root
- No automatic directory/file creation

### Previous Fixes

Previous phases have resolved all other issues:
- Phase 3: Fixed regression causing test failures
- Phase 4: Consolidated 126 workflow tests
- Phase 5: Cleaned up code and removed deprecated features
- Phase 6: Audited tests for quality (HIGH rating, no reward hacking)
- Skip Audit: Fixed import errors (21 tests enabled), resolved missing resource skips
- Final Consolidation: Removed legacy tests/infrastructure/ directory, deleted redundant test files (test_config_detection.py, test_security_constraints.py)
- Fallback Removal: Simplified detection functions, removed 13 fallback tests, home-only config

### Troubleshooting Unexpected Failures

If you encounter test failures:
1. Check if Studio is running (if test requires it)
2. Verify environment setup (Python 3.11+, dependencies installed)
3. Check for stale processes or PID files
4. Review test output for specific error messages
5. Ensure package is installed: `uv pip install -e .`

## Running Tests

### Using Make Commands

The Makefile provides convenient shortcuts:

```bash
# Run all tests with workflow health report
make test-all

# Run specific workflow tests
make test-workflow-health-check
make test-workflow-studio
make test-workflow-preferences
make test-workflow-help
make test-workflow-cli-routing

# Run agent tests
make test-agent-chat
make test-agent-shell-operations

# Run cross-workflow tests
make test-e2e
```

### Using pytest Directly

```bash
# Run all tests (standard output)
uv run pytest

# Run all tests except costly ones (recommended)
uv run pytest -m "not costly"

# Run with workflow health report
uv run pytest --workflow-health

# Run tests by marker
uv run pytest -m workflow_health_check
uv run pytest -m workflow_studio
uv run pytest -m workflow_preferences
uv run pytest -m workflow_help
uv run pytest -m workflow_cli_routing
uv run pytest -m agent_chat
uv run pytest -m agent_shell_operations
uv run pytest -m e2e
uv run pytest -m infrastructure_cli

# Combine markers
uv run pytest -m "infrastructure and not slow"
uv run pytest -m "e2e or integration"

# Run specific test file
uv run pytest tests/workflows/agent_chat/test_chat_agent.py -v

# Run with verbose output
uv run pytest -v

# Get JSON health report
uv run pytest --workflow-health-json
```

## Workflow Health Reporting

The health reporter provides system-level test status instead of individual test counts.

### Health Report Example

```bash
$ make test-all
======================== test session starts =========================
platform linux -- Python 3.12.3, pytest-8.4.2, pluggy-1.6.0
...
==================== Workflow Health Report =====================
✓ health_check: HEALTHY (61/61 tests passed)
✓ studio: HEALTHY (31/31 tests passed)
✓ preferences: HEALTHY (31/31 tests passed)
✓ help: HEALTHY (35/35 tests passed)
✓ cli_routing: HEALTHY (30/30 tests passed)
✓ agent_chat: HEALTHY (1/1 tests passed)
✓ agent_shell_operations: HEALTHY (67/67 tests passed)
✓ e2e: HEALTHY (80/80 tests passed)

Overall: 8/8 workflows healthy
```

### Status Levels

- **HEALTHY**: All tests passing (100% pass rate)
- **DEGRADED**: Some tests passing, some failing (0-99% pass rate)
- **UNHEALTHY**: All tests failing (0% pass rate)

### JSON Output

For CI/CD integration:

```bash
$ uv run pytest --workflow-health-json
{
  "workflows": [
    {
      "name": "health_check",
      "status": "HEALTHY",
      "passed": 61,
      "failed": 0,
      "total": 61
    },
    {
      "name": "studio",
      "status": "HEALTHY",
      "passed": 31,
      "failed": 0,
      "total": 31
    },
    {
      "name": "preferences",
      "status": "HEALTHY",
      "passed": 31,
      "failed": 0,
      "total": 31
    },
    {
      "name": "help",
      "status": "HEALTHY",
      "passed": 35,
      "failed": 0,
      "total": 35
    },
    {
      "name": "cli_routing",
      "status": "HEALTHY",
      "passed": 30,
      "failed": 0,
      "total": 30
    },
    {
      "name": "agent_chat",
      "status": "HEALTHY",
      "passed": 1,
      "failed": 0,
      "total": 1
    },
    {
      "name": "agent_shell_operations",
      "status": "HEALTHY",
      "passed": 67,
      "failed": 0,
      "total": 67
    },
    {
      "name": "e2e",
      "status": "HEALTHY",
      "passed": 80,
      "failed": 0,
      "total": 80
    }
  ],
  "summary": {
    "total_workflows": 8,
    "healthy": 8,
    "degraded": 0,
    "unhealthy": 0
  }
}
```

## Adding Tests for New Workflows

When adding a new workflow to the application, follow this pattern:

### 1. Create Workflow Test Package

```bash
# Create package directory
mkdir -p tests/workflows/my_new_workflow

# Add __init__.py
touch tests/workflows/my_new_workflow/__init__.py

# Create test file
touch tests/workflows/my_new_workflow/test_my_new_workflow.py
```

### 2. Add Pytest Marker

Edit `pytest.ini` and add your workflow marker:

```ini
markers =
    workflow_health_check: Health check workflow tests
    workflow_studio: Studio workflow tests
    workflow_preferences: Preferences workflow tests
    workflow_help: Help workflow tests
    workflow_cli_routing: CLI routing workflow tests
    workflow_my_new_workflow: My new workflow tests  # Add this
    agent_chat: Chat agent tests
    agent_shell_operations: Shell operations agent tests
    e2e: End-to-end tests
```

### 3. Write Tests with Marker

```python
# tests/workflows/my_new_workflow/test_my_new_workflow.py
import pytest

@pytest.mark.workflow_my_new_workflow
def test_workflow_basic_functionality():
    """Test basic workflow functionality."""
    # Your test code here
    assert True

@pytest.mark.workflow_my_new_workflow
def test_workflow_edge_case():
    """Test workflow edge case."""
    # Your test code here
    assert True
```

### 4. Add Make Target (Optional)

Edit `Makefile` to add a convenient shortcut:

```makefile
test-workflow-my-new-workflow:
	uv run pytest -m workflow_my_new_workflow
```

Update the help text:

```makefile
help:
	@echo "  make test-workflow-my-new-workflow  - Run my new workflow tests"
```

### 5. Verify Health Reporting

Run tests to verify your workflow appears in health report:

```bash
$ make test-all
==================== Workflow Health Report =====================
✓ health_check: HEALTHY (61/61 tests passed)
✓ studio: HEALTHY (31/31 tests passed)
✓ preferences: HEALTHY (31/31 tests passed)
✓ help: HEALTHY (35/35 tests passed)
✓ cli_routing: HEALTHY (30/30 tests passed)
✓ my_new_workflow: HEALTHY (2/2 tests passed)  # Your new workflow

Overall: 6/6 workflows healthy
```

## Test Markers

Tests use pytest markers to enable selective test execution.

### Active Markers (Currently Used)

The following markers are actively used throughout the test suite:

| Marker | Purpose | Example |
|--------|---------|---------|
| `workflow_health_check` | Health check workflow tests | `@pytest.mark.workflow_health_check` |
| `workflow_studio` | Studio workflow tests | `@pytest.mark.workflow_studio` |
| `workflow_preferences` | Preferences workflow tests | `@pytest.mark.workflow_preferences` |
| `workflow_help` | Help workflow tests | `@pytest.mark.workflow_help` |
| `workflow_cli_routing` | CLI routing workflow tests | `@pytest.mark.workflow_cli_routing` |
| `agent_chat` | Chat agent tests | `@pytest.mark.agent_chat` |
| `agent_shell_operations` | Shell operations agent tests | `@pytest.mark.agent_shell_operations` |
| `e2e` | End-to-end tests | `@pytest.mark.e2e` |
| `infrastructure_cli` | Cross-workflow CLI integration tests | `@pytest.mark.infrastructure_cli` |
| `cli_unification` | CLI unification tests | `@pytest.mark.cli_unification` |
| `integration` | Integration tests | `@pytest.mark.integration` |
| `slow` | Tests that take significant time | `@pytest.mark.slow` |
| `costly` | Expensive tests (real LLM calls) | `@pytest.mark.costly` |
| `requires_network` | Tests requiring network access | `@pytest.mark.requires_network` |

### Inactive Markers (Defined but Not Used)

The following marker is defined in pytest.ini but not currently used by any tests:

| Marker | Purpose | Status | Alternative |
|--------|---------|--------|-------------|
| `unit` | Unit tests (fast, isolated, no external dependencies) | **Not used** - 0 tests | Use `make test-myagents-quick` or `pytest -m "not costly"` for fast tests |

If you run `pytest -m "unit"`, you will see "504 deselected / 0 selected" because no tests currently use this marker. This is expected behavior - the project uses workflow-based organization instead.

### Using Markers

```python
import pytest

# Single marker
@pytest.mark.workflow_health_check
def test_health_check_basic():
    pass

# Multiple markers
@pytest.mark.workflow_studio
@pytest.mark.integration
def test_studio_integration():
    pass

# Conditional skip with marker
@pytest.mark.skipif(condition, reason="Reason for skipping")
@pytest.mark.agent_chat
def test_chat_agent_conditional():
    pass
```

### Parameterized Tests

Use parameterization to test multiple cases efficiently:

```python
@pytest.mark.parametrize("command,expected", [
    ("help", ["usage", "commands"]),
    ("version", ["version", "installed"]),
    ("status", ["healthy", "running"]),
])
def test_command_output(command, expected):
    result = run_command(command)
    for keyword in expected:
        assert keyword in result.lower()
```

To add a new test case, add a tuple to the parameter list:

```python
    ("new_command", ["keyword1", "keyword2"]),
```

### Marking Costly Tests

Tests that make real API calls or take significant time should be marked:

```python
@pytest.mark.costly
@pytest.mark.e2e
def test_requires_api_call():
    """Test that calls real LLM API."""
    response = call_llm_api("test prompt")
    assert response is not None
```

Run tests excluding costly ones:

```bash
uv run pytest -m "not costly"
```

## Infrastructure Tests

Cross-workflow infrastructure tests are located in `tests/workflows/infrastructure/` and use the `infrastructure_cli` marker:

```python
# tests/workflows/infrastructure/test_cli_integration.py
import pytest

# Use infrastructure_cli marker for cross-workflow tests
@pytest.mark.infrastructure_cli
def test_cli_help_command():
    """Test CLI help output across workflows."""
    # Test code here
    pass

@pytest.mark.infrastructure_cli
def test_studio_service():
    """Test studio service integration."""
    # Test code here
    pass
```

## Writing Good Tests

### Test Naming Convention

- File names: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

### Test Organization

```python
"""Module docstring explaining what this test file covers."""

import pytest
from my_module import my_function


@pytest.mark.workflow_my_workflow
def test_basic_functionality():
    """Test basic happy path."""
    result = my_function("input")
    assert result == "expected"


@pytest.mark.workflow_my_workflow
def test_edge_case():
    """Test edge case handling."""
    result = my_function("")
    assert result is None


@pytest.mark.workflow_my_workflow
def test_error_handling():
    """Test error conditions."""
    with pytest.raises(ValueError):
        my_function(None)
```

### Test Independence

Each test should be independent and not rely on other tests:

```python
# Good - each test is self-contained
@pytest.mark.agent_shell_operations
def test_file_read():
    test_file = create_test_file()  # Setup in test
    result = read_file(test_file)
    cleanup_test_file(test_file)    # Cleanup in test
    assert result is not None


# Better - use fixtures for common setup/teardown
@pytest.fixture
def test_file():
    file = create_test_file()
    yield file
    cleanup_test_file(file)


@pytest.mark.agent_shell_operations
def test_file_read_with_fixture(test_file):
    result = read_file(test_file)
    assert result is not None
```

## CI/CD Integration

### Exit Codes

- Health reporter sets exit code 1 if any workflow is not HEALTHY
- Standard pytest exit codes apply for non-health runs

### Example GitHub Actions Workflow

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Run tests with health report
        run: make test-all

      - name: Save health report
        if: always()
        run: |
          uv run pytest --workflow-health-json > test-health.json

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-health-report
          path: test-health.json
```

## Troubleshooting

### Tests Not Discovered

```bash
# Check pytest configuration
cat pytest.ini

# List all collected tests
uv run pytest --collect-only

# Verify test file naming
ls tests/**/*test*.py
```

### Workflow Not Appearing in Health Report

1. Verify marker is added to `pytest.ini`
2. Check test has marker decorator: `@pytest.mark.workflow_*`
3. Run with verbose output: `uv run pytest -v`
4. Check for typos in marker name (strict mode enabled)

### Import Errors

```bash
# Ensure package is installed in editable mode
pip install -e .

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Verify conftest.py is present in tests/
ls tests/conftest.py
```

## Migration Notes

This test structure was established on 2025-11-05. See full migration details:
- [Test Structure Migration Notes](../docs/migrations/20251105_test_structure_migration.md)

Key changes from previous structure:
- Tests organized by workflow instead of flat structure
- Workflow health reporting instead of individual test counts
- Pytest markers for selective test execution
- Make targets for common test commands
