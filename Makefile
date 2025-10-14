.PHONY: help setup install dev-install fmt lint test run-dev run-prod build clean docker-build docker-up

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Install dependencies and setup development environment
	uv sync
	uv run pre-commit install

install: ## Install production dependencies
	uv sync --no-dev

dev-install: ## Install development dependencies
	uv sync

fmt: ## Format code with black and isort
	uv run black .
	uv run isort .

lint: ## Lint code with ruff and mypy
	uv run ruff check .
	uv run mypy grodtd grodtbt

test: ## Run tests with coverage
	uv run pytest

run-dev: ## Start runtime with ENV=dev
	ENV=dev uv run python -m grodtd.app

run-prod: ## Start runtime with ENV=prod
	ENV=prod uv run python -m grodtd.app

bt: ## Run backtests with config file
	uv run python -m grodtbt.engine --config configs/backtest.yaml

docker-build: ## Build Docker image
	docker build -t grodt:latest .

docker-up: ## Start services with Docker Compose
	docker-compose up -d

clean: ## Clean up build artifacts
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
