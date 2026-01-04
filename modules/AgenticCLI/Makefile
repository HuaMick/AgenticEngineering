# AgenticCLI Makefile
# Standardized developer entrypoints using uv

.PHONY: help venv install test test-all lint format rebuild clean

# Default target
help: ## Show this help message
	@echo "AgenticCLI - Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

venv: ## Create/sync virtual environment
	UV_CACHE_DIR=/tmp/uv-cache uv sync

install: venv ## Install package in development mode
	UV_CACHE_DIR=/tmp/uv-cache uv pip install -e .

test: ## Run tests
	UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -v

test-all: ## Run full test suite with coverage
	UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -v --cov=agenticcli --cov-report=term-missing

lint: ## Run linting checks
	UV_CACHE_DIR=/tmp/uv-cache uv run ruff check src/agenticcli tests/

format: ## Format code with ruff
	UV_CACHE_DIR=/tmp/uv-cache uv run ruff format src/agenticcli tests/
	UV_CACHE_DIR=/tmp/uv-cache uv run ruff check --fix src/agenticcli tests/

rebuild: clean venv install ## Clean and reinstall

clean: ## Remove build artifacts and caches
	rm -rf .venv
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf *.egg-info
	rm -rf dist build
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
