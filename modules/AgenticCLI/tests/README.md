# AgenticCLI Test Suite

This directory contains the test suite for AgenticCLI.

## Quick Start

```bash
# Run all tests
python -m pytest tests/

# Run unit tests only (fast)
python -m pytest tests/ -m unit

# Run integration tests only
python -m pytest tests/ -m integration

# Run tests with coverage
python -m pytest tests/ --cov=agenticcli --cov-report=term-missing

# Run tests in verbose mode
python -m pytest tests/ -v
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures (cli_runner, temp_dir, temp_repo)
├── test_*.py                # Unit tests (root level)
├── integration/             # Integration tests
│   └── test_task_commands.py
└── experiments/             # Experimental/skipped tests
    └── ...
```

### Test Categories

| Directory | Marker | Description |
|-----------|--------|-------------|
| `tests/test_*.py` | `@pytest.mark.unit` | Fast, isolated unit tests |
| `tests/integration/` | `@pytest.mark.integration` | End-to-end tests requiring setup |
| `tests/experiments/` | `@pytest.mark.skip` | Experimental tests (skipped by default) |

## Pytest Markers

The following markers are configured in `pyproject.toml`:

- **unit**: Fast, isolated unit tests. Run with `-m unit`
- **integration**: Slower tests that require setup. Run with `-m integration`
- **experiment**: Experimental tests that may be skipped. Run with `-m experiment`
- **slow**: Tests that take longer to run. Exclude with `-m "not slow"`

### Marker Usage Examples

```bash
# Run only unit tests
python -m pytest tests/ -m unit

# Run only integration tests
python -m pytest tests/ -m integration

# Exclude slow tests
python -m pytest tests/ -m "not slow"

# Run unit tests but exclude slow ones
python -m pytest tests/ -m "unit and not slow"

# Run everything except experiments
python -m pytest tests/ -m "not experiment"
```

## Coverage Commands

```bash
# Basic coverage report
python -m pytest tests/ --cov=agenticcli

# Coverage with missing lines shown
python -m pytest tests/ --cov=agenticcli --cov-report=term-missing

# Generate HTML coverage report
python -m pytest tests/ --cov=agenticcli --cov-report=html
# Open htmlcov/index.html in browser

# Coverage with branch analysis
python -m pytest tests/ --cov=agenticcli --cov-branch --cov-report=term-missing
```

## Key Fixtures (conftest.py)

| Fixture | Description |
|---------|-------------|
| `cli_runner` | Runs CLI commands and returns (stdout, stderr, returncode) |
| `temp_dir` | Temporary directory that's cleaned up after test |
| `temp_repo` | Temporary git repository for testing |

### Using cli_runner

```python
def test_example(cli_runner):
    stdout, stderr, code = cli_runner(["plan", "list"])
    assert code == 0
    assert "Plans" in stdout
```

### Using CliResult (namedtuple)

```python
def test_example_result(cli_runner):
    result = cli_runner(["agent", "plan", "task", "list"])
    assert result.returncode == 0
    assert "task" in result.stdout.lower()
```

## Writing New Tests

1. **Unit tests**: Add to `tests/test_*.py` with `pytestmark = pytest.mark.unit`
2. **Integration tests**: Add to `tests/integration/` with `pytestmark = pytest.mark.integration`
3. **Experimental tests**: Add to `tests/experiments/` with `@pytest.mark.skip`

### Example Unit Test

```python
"""Tests for new feature."""

import pytest

pytestmark = pytest.mark.unit


class TestNewFeature:
    """Tests for new feature functionality."""

    def test_basic_behavior(self):
        """Test basic feature behavior."""
        assert True

    def test_with_fixture(self, temp_dir):
        """Test using temp directory fixture."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")
        assert test_file.exists()
```

## CI/CD Integration

Tests are configured to run in CI with the following recommended commands:

```bash
# CI unit tests (fast feedback)
python -m pytest tests/ -m unit --tb=short

# CI full test suite
python -m pytest tests/ -m "not experiment" --tb=short

# CI with coverage threshold
python -m pytest tests/ --cov=agenticcli --cov-fail-under=80
```
