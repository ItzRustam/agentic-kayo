#!/usr/bin/env bash
set -euo pipefail

echo "==> Setting up environment with uv and Python 3.13..."

# Ensure uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

echo "Installing Python 3.13..."
uv python install 3.13

echo "Creating virtual environment .venv..."
uv venv --python 3.13 .venv

echo "Installing dependencies from requirements.txt..."
uv pip install -r requirements.txt --python .venv/bin/python

echo "==> Setup completed successfully."
