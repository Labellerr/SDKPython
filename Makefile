.PHONY: help install clean test lint format version info

SOURCE_DIR := labellerr
PYTHON := python3
PIP := pip3

help:
	@echo "Labellerr SDK - Simple Development Commands"
	@echo "=========================================="
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  %-15s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage .pytest_cache/ .mypy_cache/

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	flake8 .

format:
	black .

build: ## Build package
	$(PYTHON) -m build

version:
	@grep '^version = ' pyproject.toml | cut -d'"' -f2 | sed 's/^/Current version: /' || echo "Version not found"

info:
	@echo "Python: $(shell $(PYTHON) --version)"
	@echo "Working directory: $(shell pwd)"
	@echo "Git branch: $(shell git branch --show-current 2>/dev/null || echo 'Not a git repository')"
	@make version

check-release: ## Check if everything is ready for release
	@echo "Checking release readiness..."
	@git status --porcelain | grep -q . && echo "❌ Git working directory is not clean" || echo "✅ Git working directory is clean"
	@git branch --show-current | grep -q "main\|develop" && echo "✅ On main or develop branch" || echo "⚠️  Not on main or develop branch"
	@make version
	@echo "✅ Release check complete"
	@echo ""
	@echo "To create a release:"
	@echo "1. Create feature branch: git checkout -b feature/LABIMP-XXXX-release-vX.X.X"
	@echo "2. Update version in pyproject.toml"
	@echo "3. Commit: git commit -m '[LABIMP-XXXX] Prepare release vX.X.X'"
	@echo "4. Push and create PR to main (patch) or develop (minor)"

integration-test:
	$(PYTHON) -m pytest  -v labellerr_integration_case_tests.py

pre-commit-install:
	pip install pre-commit
	pre-commit install
