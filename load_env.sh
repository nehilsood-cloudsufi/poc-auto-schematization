#!/bin/bash
# Source this file to load .env variables into your shell session
# Usage: source load_env.sh

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load .env file
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "Loading environment variables from .env..."
    set -a  # Automatically export all variables
    source "$SCRIPT_DIR/.env"
    set +a  # Disable automatic export
    echo "✓ Environment variables loaded"
    echo "  GROUND_TRUTH_REPO=$GROUND_TRUTH_REPO"
    echo "  PYTHONPATH=$PYTHONPATH"
else
    echo "Error: .env file not found at $SCRIPT_DIR/.env"
fi
