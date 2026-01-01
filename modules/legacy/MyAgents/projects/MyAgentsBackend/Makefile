.PHONY: venv install sync clean test lint run help test-workflow-health-check test-workflow-studio test-workflow-preferences test-workflow-help test-workflow-cli-routing test-agent-chat test-agent-shell-operations test-e2e test-all rebuild-myagents test-myagents test-myagents-parallel update-test-myagents

help:
	@echo "Available commands:"
	@echo "  make venv                           - Create a new virtual environment"
	@echo "  make install                        - Install project dependencies"
	@echo "  make run                            - Run the application"
	@echo "  make test-workflow-health-check     - Run health check workflow tests"
	@echo "  make test-workflow-studio           - Run studio workflow tests"
	@echo "  make test-workflow-preferences      - Run preferences workflow tests"
	@echo "  make test-workflow-help             - Run help workflow tests"
	@echo "  make test-workflow-cli-routing      - Run CLI routing workflow tests"
	@echo "  make test-agent-chat                - Run chat agent tests"
	@echo "  make test-agent-shell-operations    - Run shell operations agent tests"
	@echo "  make test-e2e                       - Run end-to-end tests"
	@echo "  make test-all                       - Run all tests with workflow health report"
	@echo "  make rebuild-myagents               - Rebuild and reinstall myagents package"
	@echo "  make test-myagents                  - Run myagents test suite"
	@echo "  make test-myagents-parallel         - Run myagents test suite in parallel using Docker"

venv:
	uv venv

install:
	uv sync

run:
	uv run python -m main

# Test commands
test-workflow-health-check:
	uv run pytest -m workflow_health_check

test-workflow-studio:
	uv run pytest -m workflow_studio

test-workflow-preferences:
	uv run pytest -m workflow_preferences

test-workflow-help:
	uv run pytest -m workflow_help

test-workflow-cli-routing:
	uv run pytest -m workflow_cli_routing

test-agent-chat:
	uv run pytest -m agent_chat

test-agent-shell-operations:
	uv run pytest -m agent_shell_operations

test-e2e:
	uv run pytest -m e2e

test-all:
	uv run pytest tests/ --workflow-health

# MyAgents package management commands
rebuild-myagents:
	export PIP_NO_INPUT=1 && myagents rebuild

test-myagents:
	uv run pytest tests/

test-myagents-quick:
	uv run pytest tests/ -x --maxfail=1 -k "test_help or test_version"

test-myagents-parallel:
	@echo "Running parallel test execution using Docker..."
	./scripts/run-parallel-tests.sh

update-test-myagents: rebuild-myagents test-myagents
	@echo "MyAgents rebuild and test complete"
