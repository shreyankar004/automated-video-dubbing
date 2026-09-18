#!/usr/bin/env bash
# Sets up backend + frontend for local development on Linux/macOS.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Checking prerequisites =="
command -v python3 >/dev/null || { echo "Python 3.11+ is required."; exit 1; }
command -v ffmpeg >/dev/null || echo "WARNING: ffmpeg not found on PATH. Install it before running the pipeline."
command -v node >/dev/null || echo "NOTE: Node.js not found (only needed if you replace the static frontend)."

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

echo "== Creating virtual environment =="
python3 -m venv .venv
source .venv/bin/activate

echo "== Installing backend dependencies =="
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "== Preparing directories =="
mkdir -p data/downloads data/audio data/jobs data/output

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

echo ""
echo "Setup complete."
echo "Next steps:"
echo "  source .venv/bin/activate"
echo "  uvicorn app.main:app --reload --app-dir backend"
echo "  # or: python cli/cli.py \"https://www.youtube.com/watch?v=...\""
