# Local Testing Guide

Detailed guide for running tests locally, including Docker-based testing.

## Local pytest (Direct)

### When It Works
- Testing a single workflow package
- Tests that don't import `agent-gcptoolkit`
- Quick iteration during development

### When It Fails
- Tests requiring `agent-gcptoolkit` dependency
- Full test suite runs
- Cross-package integration tests

### Commands

```bash
# Install dev dependencies
uv sync --dev

# Run specific workflow
pytest tests/workflows/cli_unification/ -v

# Run with coverage
pytest --cov=backend --cov=frontend tests/

# Run excluding costly tests
pytest -m "not costly" tests/
```

## Docker Testing (Recommended for Full Validation)

Docker solves the workspace dependency issue by rewriting `pyproject.toml` inside the container.

### Prerequisites
1. Docker installed and running
2. Service account key at expected path (or set `GCP_SA_KEY_PATH`)

### Running Docker Tests

From the parent directory (`/home/code/myagents`):

```bash
# Run all test suites in parallel
WORKTREE_NAME=MyAgents-staging docker-compose -f MyAgents-staging/docker-compose.test.yml up --build

# Run specific test suite
WORKTREE_NAME=MyAgents-staging docker-compose -f MyAgents-staging/docker-compose.test.yml up --build test-cli-unification

# Clean up containers
docker-compose -f MyAgents-staging/docker-compose.test.yml down
```

### Available Test Services

| Service | Test Path |
|---------|-----------|
| `test-cli-unification` | `tests/workflows/cli_unification/` |
| `test-coding-agent` | `tests/workflows/agent_chat/` |
| `test-infrastructure-workflow` | `tests/workflows/infrastructure/` |
| `test-packaging` | `tests/workflows/e2e/` |
| `test-integration-file-ops` | `tests/integration/file_operations/` |

### How Docker Fixes the Dependency Issue

The `Dockerfile.test` automatically rewrites the workspace reference:

```dockerfile
# Changes workspace = true to path reference
RUN sed -i 's|agent-gcptoolkit = { workspace = true }|agent-gcptoolkit = { path = "./Agent-GCPtoolkit", editable = true }|g' pyproject.toml
```

This mirrors exactly what CI/CD does.

## Test Environment Decision Tree

```
Need to run tests?
│
├─► Single workflow, no gcptoolkit imports?
│   └─► Use local pytest
│
├─► Full validation needed?
│   └─► Use Docker (mirrors CI)
│
└─► Final validation before merge?
    └─► Push to trigger CI/CD
```

## Troubleshooting

### Import Error: agent-gcptoolkit

**Problem**: `ModuleNotFoundError: No module named 'agent_gcptoolkit'`

**Cause**: Workspace dependency can't resolve across worktrees locally.

**Solution**: Use Docker testing:
```bash
cd /home/code/myagents
WORKTREE_NAME=MyAgents-staging docker-compose -f MyAgents-staging/docker-compose.test.yml up --build
```

### Docker Build Fails

**Problem**: Docker build fails to find files

**Solution**: Ensure you're running from the parent directory:
```bash
cd /home/code/myagents  # NOT MyAgents-staging
WORKTREE_NAME=MyAgents-staging docker-compose -f MyAgents-staging/docker-compose.test.yml up --build
```

### Tests Skip Unexpectedly

**Problem**: Tests skip with "Studio not running"

**Solution**: Start LangGraph Studio before tests:
```bash
myagents studio start
pytest tests/workflows/studio/ -v
myagents studio stop
```

## Test Markers Reference

| Marker | Purpose | Example |
|--------|---------|---------|
| `unit` | Fast, isolated tests | `pytest -m unit` |
| `integration` | Component interaction tests | `pytest -m integration` |
| `e2e` | Full workflow tests | `pytest -m e2e` |
| `costly` | Tests with real API calls | `pytest -m costly` |
| `slow` | Time-consuming tests | `pytest -m slow` |

### Combining Markers

```bash
# Unit tests, no API calls
pytest -m "unit and not costly" tests/

# All except slow tests
pytest -m "not slow" tests/

# Integration or e2e
pytest -m "integration or e2e" tests/
```

## Coverage

```bash
# Run with coverage report
pytest --cov=backend --cov=frontend --cov=myagents tests/ --cov-report=term

# Generate HTML coverage report
pytest --cov=backend tests/ --cov-report=html
open htmlcov/index.html
```

## Related Documentation

- [CICD_README.md](../CICD_README.md) - Cloud Build pipeline details
- [tests/README.md](/tests/README.md) - Full test structure reference

