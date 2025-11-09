#!/bin/bash
# Run Simulator API service
# Make sure virtual environment is activated

cd "$(dirname "$0")/../.."

# Activate virtual environment if not already activated
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -f .venv/bin/activate ]; then
        source .venv/bin/activate
    else
        echo "Error: Virtual environment not found. Please create it first:"
        echo "  python -m venv .venv"
        echo "  source .venv/bin/activate"
        echo "  pip install -e ."
        exit 1
    fi
fi

# Run the service
python -m uvicorn apps.simulator_api.main:app --host 0.0.0.0 --port 8000

