#!/bin/bash

# Initialize and configure Python virtual environment (.venv) via uv
# Usage: ./setup-venv.sh [python-version] [venv-directory]
# Examples:
#   ./setup-venv.sh              # Use default Python and .venv
#   ./setup-venv.sh 3.11         # Use specific Python version
#   ./setup-venv.sh 3.11 .venv   # Use specific version and directory

set -euo pipefail

PYTHON_VERSION="${1:-}"
VENV_DIR="${2:-.venv}"

# Ensure uv is available
if ! command -v uv &>/dev/null; then
    echo "Error: uv not found" >&2
    echo "Install it with one of:" >&2
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    echo "  portunix install uv" >&2
    exit 1
fi

echo "Using: $(uv --version)"

# Check if venv already exists
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists at $VENV_DIR"
    read -rp "Recreate it? (y/n): " answer
    if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
        echo "Removing existing $VENV_DIR..."
        rm -rf "$VENV_DIR"
    else
        echo "Keeping existing environment"
        echo "Activate with: source $VENV_DIR/bin/activate"
        exit 0
    fi
fi

# Create virtual environment
echo "Creating virtual environment in $VENV_DIR..."
if [ -n "$PYTHON_VERSION" ]; then
    uv venv --python "$PYTHON_VERSION" "$VENV_DIR"
else
    uv venv "$VENV_DIR"
fi

# Install dependencies from available config files
DEPS_INSTALLED=false

if [ -f "pyproject.toml" ]; then
    echo "Syncing dependencies from pyproject.toml..."
    VIRTUAL_ENV="$VENV_DIR" uv sync
    DEPS_INSTALLED=true
elif [ -f "requirements.txt" ]; then
    echo "Installing dependencies from requirements.txt..."
    VIRTUAL_ENV="$VENV_DIR" uv pip install -r requirements.txt
    DEPS_INSTALLED=true
fi

if [ -f "requirements-dev.txt" ]; then
    echo "Installing dev dependencies from requirements-dev.txt..."
    VIRTUAL_ENV="$VENV_DIR" uv pip install -r requirements-dev.txt
    DEPS_INSTALLED=true
fi

if [ "$DEPS_INSTALLED" = false ]; then
    echo "No dependency files found (pyproject.toml, requirements.txt)"
fi

# Verify setup
echo ""
echo "Virtual environment ready:"
echo "  Location: $VENV_DIR"
echo "  Python:   $("$VENV_DIR/bin/python" --version 2>&1)"
echo ""
echo "Activate with:"
echo "  source $VENV_DIR/bin/activate"
echo ""
echo "Or run commands without activation:"
echo "  uv run <command>"
