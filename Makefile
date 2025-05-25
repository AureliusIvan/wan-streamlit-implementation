.PHONY: help install run clean test lint format setup dev-install check all sync lock

# Project variables
APP_NAME := main.py
PORT := 8501

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Default target
help:
	@echo "$(GREEN)WAN Video Generator - Available Commands (using uv):$(NC)"
	@echo ""
	@echo "$(YELLOW)Setup & Installation:$(NC)"
	@echo "  make setup          - Create virtual environment and install dependencies with uv"
	@echo "  make install        - Install production dependencies"
	@echo "  make dev-install    - Install development dependencies"
	@echo "  make sync           - Sync dependencies from pyproject.toml"
	@echo "  make lock           - Update uv.lock file"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make run            - Run the Streamlit application"
	@echo "  make dev            - Run in development mode with auto-reload"
	@echo "  make check          - Run all code quality checks"
	@echo "  make lint           - Run linting checks"
	@echo "  make format         - Format code with black"
	@echo "  make test           - Run tests"
	@echo ""
	@echo "$(YELLOW)Maintenance:$(NC)"
	@echo "  make clean          - Clean temporary files and cache"
	@echo "  make all            - Run setup, checks, and tests"

# Check if uv is installed
check-uv:
	@which uv > /dev/null || (echo "$(RED)Error: uv is not installed. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh$(NC)" && exit 1)

# Setup virtual environment and install dependencies with uv
setup: check-uv
	@echo "$(GREEN)Setting up virtual environment with uv...$(NC)"
	uv venv
	@echo "$(GREEN)Installing dependencies with uv...$(NC)"
	uv sync
	@echo "$(GREEN)Setup complete! Activate with: source .venv/bin/activate$(NC)"

# Install production dependencies
install: check-uv
	@echo "$(GREEN)Installing production dependencies with uv...$(NC)"
	uv sync --no-dev

# Install development dependencies
dev-install: check-uv
	@echo "$(GREEN)Installing all dependencies (including dev) with uv...$(NC)"
	uv sync

# Sync dependencies from pyproject.toml
sync: check-uv
	@echo "$(GREEN)Syncing dependencies with uv...$(NC)"
	uv sync

# Update lock file
lock: check-uv
	@echo "$(GREEN)Updating uv.lock file...$(NC)"
	uv lock

# Run the Streamlit application
run:
	@echo "$(GREEN)Starting Streamlit application...$(NC)"
	uv run streamlit run $(APP_NAME) --server.port $(PORT)

# Run in development mode
dev:
	@echo "$(GREEN)Starting Streamlit in development mode...$(NC)"
	uv run streamlit run $(APP_NAME) --server.port $(PORT) --server.runOnSave true

# Run linting
lint:
	@echo "$(GREEN)Running linting checks...$(NC)"
	uv run flake8 . --max-line-length=88 --extend-ignore=E203,W503

# Format code
format:
	@echo "$(GREEN)Formatting code with black...$(NC)"
	uv run black . --line-length=88

# Run tests
test:
	@echo "$(GREEN)Running tests...$(NC)"
	uv run pytest -v

# Run all code quality checks
check: lint
	@echo "$(GREEN)All checks completed!$(NC)"

# Clean temporary files
clean:
	@echo "$(GREEN)Cleaning temporary files...$(NC)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.tmp" -delete
	find . -type f -name "temp_uploaded_image.*" -delete
	find . -type f -name "mock_video_for_*.mp4" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf .venv
	@echo "$(GREEN)Cleanup complete!$(NC)"

# Run everything
all: setup check test
	@echo "$(GREEN)All tasks completed successfully!$(NC)"

# Quick development setup
quick-start: install run

# Show project status
status:
	@echo "$(GREEN)Project Status:$(NC)"
	@echo "Python version: $(shell python --version 2>/dev/null || echo 'Not available')"
	@echo "uv version: $(shell uv --version 2>/dev/null || echo 'Not installed')"
	@echo "Streamlit version: $(shell uv run streamlit version 2>/dev/null || echo 'Not installed')"
	@echo "Main application: $(APP_NAME)"
	@echo "Default port: $(PORT)"

# Install uv (if not already installed)
install-uv:
	@echo "$(GREEN)Installing uv...$(NC)"
	@which uv > /dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
	@echo "$(GREEN)uv installation complete!$(NC)"

# Add specific package
add:
	@echo "$(GREEN)Adding package with uv...$(NC)"
	@read -p "Enter package name: " package; \
	uv add $$package

# Add development package
add-dev:
	@echo "$(GREEN)Adding development package with uv...$(NC)"
	@read -p "Enter package name: " package; \
	uv add --dev $$package

# Remove package
remove:
	@echo "$(GREEN)Removing package with uv...$(NC)"
	@read -p "Enter package name: " package; \
	uv remove $$package

# Show dependency tree
tree:
	@echo "$(GREEN)Showing dependency tree...$(NC)"
	uv tree

# Export requirements for compatibility
export-requirements:
	@echo "$(GREEN)Exporting requirements.txt for compatibility...$(NC)"
	uv pip freeze > requirements.txt.backup
	@echo "$(GREEN)Requirements exported to requirements.txt.backup$(NC)"
