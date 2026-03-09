# AgenticCLI Makefile
# Standardized developer entrypoints using uv

.PHONY: help venv install test test-fast test-seq test-all lint format rebuild clean

# Default target
help: ## Show this help message
	@echo "AgenticCLI - Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

venv: ## Create/sync virtual environment
	UV_CACHE_DIR=/tmp/uv-cache uv sync

install: venv ## Install package in development mode
	UV_CACHE_DIR=/tmp/uv-cache uv pip install -e .

test: ## Run tests in parallel (uses pyproject.toml addopts)
	UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/

test-fast: ## Run only changed tests in parallel (testmon + xdist, no -m filter)
	UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -o "addopts=" --testmon -n auto --dist loadgroup

test-seq: ## Run tests sequentially (for debugging, no testmon)
	UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -v -o "addopts=-m 'not uat'" -p no:testmon

test-all: ## Run full test suite with coverage (sequential, no testmon)
	UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -v -o "addopts=-m 'not uat'" -p no:testmon --cov=agenticcli --cov-report=term-missing

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
	rm -f .testmondata .testmondata-shm .testmondata-wal
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
