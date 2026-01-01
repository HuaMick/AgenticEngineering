# Testing Guide

Quick reference for running tests. For detailed information, see the linked documents.

## Quick Start

```bash
# Run all tests (recommended)
make test-all

# Run specific workflow tests
pytest tests/workflows/cli_unification/ -v
pytest tests/workflows/e2e/ -v
```

## Testing Options

| Method | When to Use | Command |
|--------|-------------|---------|
| **Local pytest** | Single workflow tests, fast iteration | `pytest tests/workflows/<name>/ -v` |
| **Docker** | Full validation, mirrors CI exactly | See [LOCAL_TESTING.md](./LOCAL_TESTING.md) |
| **CI/CD** | Final validation before merge | Push to trigger Cloud Build |

## Local Testing Limitation

⚠️ **Workspace Dependency Issue**: Local tests may fail due to `agent-gcptoolkit` workspace dependency. Use Docker or CI for full validation.

```bash
# If local tests fail with import errors, use Docker:
cd /home/code/myagents
WORKTREE_NAME=MyAgents-staging docker-compose -f MyAgents-staging/docker-compose.test.yml up --build
```

## Test Markers

Run specific test types:

```bash
# Unit tests only (fast, no API calls)
pytest -m "unit and not costly" tests/

# Skip expensive LLM tests
pytest -m "not costly" tests/

# Run only costly tests (requires API keys)
pytest -m "costly" tests/
```

## Test Structure

```
tests/
├── workflows/           # Per-workflow test packages
│   ├── cli_unification/ # CLI tests
│   ├── e2e/             # End-to-end tests
│   ├── agent_chat/      # Agent tests
│   └── ...
└── integration/         # Legacy integration tests
```

## Detailed Documentation

| Topic | Document |
|-------|----------|
| Local & Docker testing | [LOCAL_TESTING.md](./LOCAL_TESTING.md) |
| CI/CD pipeline | [../CICD_README.md](../CICD_README.md) |
| **User stories (UAT)** | [/docs/userstories/MyAgents/](/docs/userstories/MyAgents/) |
| Blind test scenarios | [blind_test_scenarios.md](./blind_test_scenarios.md) |
| User journey testing | [user_journey_map.md](./user_journey_map.md) |
| Full test reference | [tests/README.md](/tests/README.md) |

