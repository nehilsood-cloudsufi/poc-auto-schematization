#!/bin/bash
# Wrapper script to load .env variables and run the PVMAP pipeline

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load environment variables from .env file
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo "Loading environment variables from .env..."
    export $(cat "$SCRIPT_DIR/.env" | grep -v '^#' | grep -v '^$' | xargs)
else
    echo "Warning: .env file not found at $SCRIPT_DIR/.env"
fi

# Run the pipeline with all arguments passed to this script
echo "Running PVMAP pipeline..."
python3 "$SCRIPT_DIR/run_pvmap_pipeline.py" "$@"
