.PHONY: help install dev test lint typecheck format clean build

help:
	@echo "Available targets:"
	@echo "  install    - Install package"
	@echo "  dev        - Install package with dev dependencies"
	@echo "  test       - Run tests"
	@echo "  lint       - Run linter"
	@echo "  typecheck  - Run type checker"
	@echo "  format     - Format code"
	@echo "  clean      - Clean build artifacts"
	@echo "  build      - Build package"

install:
	uv sync

dev:
	uv sync --dev

test:
	uv run pytest

test-cov:
	uv run pytest --cov=agent_remote --cov-report=html

lint:
	uv run ruff check src/ tests/

lint-fix:
	uv run ruff check --fix src/ tests/

typecheck:
	uv run mypy src/

format:
	uv run ruff format src/ tests/

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

build:
	uv build
