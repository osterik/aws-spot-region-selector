.DEFAULT_GOAL := help

VENV := .venv
PYTHON := $(VENV)/bin/python
APP := $(VENV)/bin/spot-region-selector

.PHONY: help init test lint format-check run

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "; print "Usage: make <target>\n"} /^[a-zA-Z_-]+:.*## / {printf "  %-13s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

init: ## Create .venv, install development dependencies, and prepare config.yaml
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install -e '.[dev]'
	@test -e config.yaml || cp config.example.yaml config.yaml

test: ## Run the pytest suite
	$(PYTHON) -m pytest

lint: ## Run Ruff lint checks
	$(VENV)/bin/ruff check .

format-check: ## Check Ruff formatting without changing files
	$(VENV)/bin/ruff format --check .

run: ## Run using ./config.yaml (ARGS may override CLI options)
	$(APP) $(ARGS)
