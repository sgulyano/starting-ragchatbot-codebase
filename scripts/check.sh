#!/bin/bash
# Run all code quality checks (no files are modified). Exits non-zero on failure.
set -e
cd "$(dirname "$0")/.."
echo "Checking formatting with black..."
uv run black --check --diff backend main.py
echo "All quality checks passed."
