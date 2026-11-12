#!/usr/bin/env bash
# One-command launcher:  ./ps.sh   ->  http://127.0.0.1:8000
set -e
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python || true)
[ -z "$PY" ] && { echo "Python 3.10+ is required."; exit 1; }

# Tesseract (needed for your own scans; the bundled sample works without it)
if ! command -v tesseract >/dev/null 2>&1; then
  echo "Tesseract not found, trying to install it..."
  if   command -v apt-get >/dev/null 2>&1; then sudo apt-get install -y tesseract-ocr || true
  elif command -v brew    >/dev/null 2>&1; then brew install tesseract || true
  else echo "Install Tesseract manually (see README). Continuing; only the sample will work."; fi
fi

# Virtual environment + dependencies (reinstalls only when requirements.txt changes)
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate   # Git Bash on Windows
if ! cmp -s requirements.txt .venv/.req_installed; then
  pip install -q -r requirements.txt && cp requirements.txt .venv/.req_installed
fi

echo "Starting at http://127.0.0.1:${PORT:-8000}  (Ctrl+C to stop)"
exec python run.py
