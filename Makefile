# IndiBrew Vendor Risk Monitor — Makefile
# Usage: make <target>

.PHONY: install run run-full test lint typecheck clean help

PYTHON    := python3
DATA_DIR  := data/sample
OUTPUT_DIR := reports

help:           ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:        ## Install all dependencies
	pip install -r requirements.txt

run:            ## Run full pipeline on sample data
	$(PYTHON) orchestrator.py \
	  --data-dir $(DATA_DIR) \
	  --output-dir $(OUTPUT_DIR) \
	  --verbose

run-full:       ## Run pipeline on full production data (set DATA_DIR env var)
	$(PYTHON) orchestrator.py \
	  --data-dir $(DATA_DIR) \
	  --output-dir $(OUTPUT_DIR) \
	  --verbose

dry-run:        ## Validate data only (no file writes)
	$(PYTHON) orchestrator.py \
	  --data-dir $(DATA_DIR) \
	  --dry-run \
	  --verbose

test:           ## Run all unit tests with coverage
	pytest tests/ -v --cov=agents --cov=config --cov-report=term-missing

lint:           ## Lint with ruff
	ruff check agents/ config/ orchestrator.py tests/

typecheck:      ## Type-check with mypy
	mypy agents/ config/ orchestrator.py --ignore-missing-imports

clean:          ## Remove generated reports
	rm -rf $(OUTPUT_DIR)/*.html $(OUTPUT_DIR)/*.md

clean-all:      ## Remove all generated files including __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type f -name "*.pyc" -delete; \
	rm -rf $(OUTPUT_DIR)/*.html $(OUTPUT_DIR)/*.md .mypy_cache .ruff_cache
