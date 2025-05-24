.PHONY: help install run clean test lint format setup dev-install check all

# Default Python interpreter
PYTHON := python3
PIP := pip3

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
	@echo "$(GREEN)WAN Video Generator - Available Commands:$(NC)"
	@echo ""
	@echo "$(YELLOW)Setup & Installation:$(NC)"
	@echo "  make setup          - Create virtual environment and install dependencies"
	@echo "  make install        - Install production dependencies"
	@echo "  make dev-install    - Install development dependencies"
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
	@echo "  make freeze         - Update requirements.txt with current packages"
	@echo "  make all            - Run setup, checks, and tests"


# Active virtual environment
active-venv:
	source ./.env/bin/activate

# Setup virtual environment and install dependencies
setup:
	@echo "$(GREEN)Setting up virtual environment...$(NC)"
	$(PYTHON) -m venv venv
	@echo "$(GREEN)Activating virtual environment and installing dependencies...$(NC)"
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	@echo "$(GREEN)Setup complete! Activate with: source venv/bin/activate$(NC)"

# Install production dependencies
install:
	@echo "$(GREEN)Installing production dependencies...$(NC)"
	$(PIP) install -r requirements.txt

# Install development dependencies
dev-install: install
	@echo "$(GREEN)Installing development dependencies...$(NC)"
	$(PIP) install black flake8 pytest streamlit-dev pytest-mock

# Run the Streamlit application
run:
	@echo "$(GREEN)Starting Streamlit application...$(NC)"
	streamlit run $(APP_NAME) --server.port $(PORT)

# Run in development mode
dev:
	@echo "$(GREEN)Starting Streamlit in development mode...$(NC)"
	streamlit run $(APP_NAME) --server.port $(PORT) --server.runOnSave true

# Run linting
lint:
	@echo "$(GREEN)Running linting checks...$(NC)"
	flake8 $(APP_NAME) --max-line-length=88 --extend-ignore=E203,W503

# Format code
format:
	@echo "$(GREEN)Formatting code with black...$(NC)"
	black $(APP_NAME) --line-length=88

# Run tests
test:
	@echo "$(GREEN)Running tests...$(NC)"
	pytest -v

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
	@echo "$(GREEN)Cleanup complete!$(NC)"

# Freeze current environment to requirements.txt
freeze:
	@echo "$(GREEN)Updating requirements.txt...$(NC)"
	$(PIP) freeze > requirements.txt

# Run everything
all: setup check test
	@echo "$(GREEN)All tasks completed successfully!$(NC)"

# Quick development setup
quick-start: install run

# Show project status
status:
	@echo "$(GREEN)Project Status:$(NC)"
	@echo "Python version: $(shell $(PYTHON) --version)"
	@echo "Streamlit version: $(shell streamlit version 2>/dev/null || echo 'Not installed')"
	@echo "Main application: $(APP_NAME)"
	@echo "Default port: $(PORT)"