# AgenticCLI Test Suite

This directory contains the test suite for AgenticCLI.

## Quick Start

```bash
# Run all tests (parallel, excludes UAT — default from pyproject.toml addopts)
make test

# Run only changed tests in parallel (testmon + xdist, no marker filter)
make test-fast

# Run tests sequentially (for debugging)
make test-seq

# Run full test suite with coverage (sequential)
make test-all
```

Or using pytest directly:

```bash
# Parallel (uses pyproject.toml addopts: -m 'not uat' -n auto --dist loadgroup)
uv run pytest tests/

# Sequential — override addopts, disable testmon
uv run pytest tests/ -v -o "addopts=-m 'not uat'" -p no:testmon

# Specific worker count
uv run pytest tests/ -n 4 --dist loadgroup

# Disable xdist for a single file (for debugging)
uv run pytest tests/test_foo.py -p no:xdist
```

## Parallel Testing (pytest-xdist)

Tests run in parallel by default using `pytest-xdist` with `-n auto` (one worker per CPU).

`pyproject.toml` addopts: `-m 'not uat' -n auto --dist loadgroup`

### Key Configuration

- **Distribution mode**: `--dist loadgroup` — keeps tests with the same `xdist_group` marker on the same worker
- **Integration tests**: Serialized automatically — `tests/integration/conftest.py` has a `pytest_collection_modifyitems` hook that adds `@pytest.mark.xdist_group("integration")` to every item collected from that directory, preventing tmux session conflicts
- **Worker isolation**: Each xdist worker is a separate process with its own `tmp_path`, CWD, and TinyDB instance

### Debugging Parallel Issues

```bash
# Run sequentially (no xdist, no testmon)
make test-seq

# Run with a specific worker count
uv run pytest tests/ -n 4 --dist loadgroup -p no:testmon

# Run a single test file sequentially (override addopts entirely)
uv run pytest tests/test_foo.py -p no:xdist -v
```

## pytest-testmon (Selective Testing)

`make test-fast` enables testmon to track which tests are affected by code changes and re-run only those.

```bash
# Changed-tests-only run (testmon + xdist, no marker filter)
make test-fast

# Force full re-run by deleting the testmon database
rm -f .testmondata .testmondata-shm .testmondata-wal
uv run pytest tests/
```

Note: testmon is NOT active in `make test` (the default). It is only enabled in `make test-fast`.

## Makefile Targets

| Target | Command | Description |
|--------|---------|-------------|
| `make test` | `pytest tests/` | Parallel, excludes UAT (pyproject.toml addopts) |
| `make test-fast` | `pytest tests/ --testmon -n auto --dist loadgroup` | testmon + xdist, no marker filter |
| `make test-seq` | `pytest tests/ -v -o "addopts=-m 'not uat'" -p no:testmon` | Sequential, excludes UAT, no testmon |
| `make test-all` | `pytest tests/ -v ... --cov=agenticcli` | Full suite with coverage, sequential |
| `make lint` | `ruff check src/ tests/` | Run ruff linting |
| `make format` | `ruff format ...` | Format code with ruff |
| `make clean` | | Remove build artifacts, caches, and testmon data |

## Test Structure

```
tests/
├── conftest.py              # Shared autouse fixtures (_isolate_tinydb, _block_real_ntfy)
├── test_*.py                # Unit/workflow tests (root level, run in parallel)
├── integration/             # Integration tests
│   ├── conftest.py          # xdist_group("integration") hook — serializes all integration tests
│   └── test_*.py
└── experiments/             # Experimental/skipped tests
    └── ...
```

### Test Categories

| Directory | Marker | Description |
|-----------|--------|-------------|
| `tests/test_*.py` | `@pytest.mark.unit` | Fast, isolated unit and workflow tests |
| `tests/integration/` | auto-grouped via hook | End-to-end tests; serialized on one xdist worker |
| `tests/experiments/` | `@pytest.mark.skip` | Experimental tests (skipped by default) |

## Pytest Markers

Configured in `pyproject.toml`:

- **unit**: Fast, isolated unit tests. Run with `-m unit`
- **integration**: Slower tests that require setup. Run with `-m integration`
- **experiment**: Experimental tests that may be skipped. Run with `-m experiment`
- **slow**: Tests that take longer to run. Exclude with `-m "not slow"`
- **uat**: Acceptance tests excluded from default runs. Run with `-m uat`
- **ntfy**: Tests exercising ntfy notification paths (require mock HTTP)

## Key Fixtures (conftest.py)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `_isolate_tinydb` | autouse/function | Redirects TinyDB to a per-test `tmp_path` DB; xdist-safe because `tmp_path` is per-process |
| `_block_real_ntfy` | autouse/function | Prevents real ntfy HTTP calls during tests |
| `cli_runner` | function | Runs CLI commands via subprocess, returns `(stdout, stderr, returncode)` |
| `temp_dir` | function | Temporary directory, cleaned up after test |
| `temp_repo` | function | Temporary git repository |
| `mock_cwd` | function | Changes CWD to `temp_repo` |
| `tinydb_populator` | function | Populates the isolated TinyDB with test data |

### TinyDB Isolation

`_isolate_tinydb` is an autouse fixture that patches the TinyDB path to `tmp_path / "test.db"` for every test. Because `tmp_path` is unique per test and each xdist worker is a separate process, there are no cross-test or cross-worker DB conflicts.

### Using cli_runner

```python
def test_example(cli_runner):
    stdout, stderr, code = cli_runner(["epic", "list"])
    assert code == 0
    assert "Epics" in stdout
```

## Writing New Tests

1. **Unit tests**: Add to `tests/test_*.py` — run in parallel automatically.
2. **Integration tests**: Add to `tests/integration/` — automatically serialized on one xdist worker via the `pytest_collection_modifyitems` hook in `tests/integration/conftest.py`. No manual `xdist_group` marker needed.
3. **Experimental tests**: Add to `tests/experiments/` with `@pytest.mark.skip`.

## CI/CD Integration

```bash
# CI fast feedback (parallel, excludes UAT)
uv run pytest tests/ -m 'not uat' -n auto --dist loadgroup --tb=short

# CI full suite with coverage (sequential for accurate coverage)
uv run pytest tests/ -m 'not uat' -p no:testmon -p no:xdist --cov=agenticcli --cov-fail-under=80
```
