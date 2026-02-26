#!/bin/bash
set -e
echo "Activating virtual environment..."
source "$(dirname "$0")/.venv/bin/activate"
echo ""
echo "ClefSwap backend starting at http://localhost:8000"
echo "Frontend: open frontend/index.html in your browser"
echo ""
exec uvicorn backend.main:app --reload --port 8000 --log-level info
