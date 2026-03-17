#!/usr/bin/env bash
# check_nlm.sh — Verify NotebookLM connection before running the pipeline.
#
# Usage:
#   bash notebooklm/check_nlm.sh                        # Uses default DC notebook
#   bash notebooklm/check_nlm.sh --notebook-id=<ID>     # Custom notebook
#
# Prerequisites:
#   - Chrome running with CDP on port 9222 (or start it here)
#   - notebooklm-py authenticated (cookies valid)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default DC notebook
NOTEBOOK_ID="3d07c6fa-9e36-43e8-91cd-bbc690f32e58"

# Parse arguments
for arg in "$@"; do
    case $arg in
        --notebook-id=*)
            NOTEBOOK_ID="${arg#*=}"
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: bash notebooklm/check_nlm.sh [--notebook-id=<ID>]"
            exit 1
            ;;
    esac
done

# Auto-detect venv
if [ -d "$PROJECT_ROOT/.cloudtop_venv" ]; then
    VENV="$PROJECT_ROOT/.cloudtop_venv"
elif [ -d "$PROJECT_ROOT/.venv" ]; then
    VENV="$PROJECT_ROOT/.venv"
else
    echo "ERROR: No virtual environment found (.cloudtop_venv or .venv)"
    exit 1
fi

PYTHON="$VENV/bin/python"
echo "Using Python: $PYTHON"
echo "Notebook ID: $NOTEBOOK_ID"

# Check Chrome CDP on port 9222
echo ""
echo "Checking Chrome CDP on port 9222..."
if curl -s --max-time 2 http://localhost:9222/json/version > /dev/null 2>&1; then
    echo "  Chrome CDP: OK"
else
    echo "  Chrome CDP: NOT RUNNING"
    echo ""
    echo "  Starting Chrome with CDP..."

    # Kill stale Chrome (but not Chrome Remote Desktop)
    pkill -f 'chrome.*--remote-debugging-port=9222' 2>/dev/null || true
    sleep 1

    # Determine Chrome binary
    if [ -f "/usr/bin/google-chrome" ]; then
        CHROME="/usr/bin/google-chrome"
    elif [ -f "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
        CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    else
        echo "ERROR: Chrome not found. Please start Chrome manually with:"
        echo "  google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-debug"
        exit 1
    fi

    "$CHROME" \
        --remote-debugging-port=9222 \
        --user-data-dir=/tmp/chrome-debug-nlm \
        --no-first-run \
        --no-default-browser-check \
        &>/dev/null &

    # Wait for CDP
    for i in $(seq 1 15); do
        if curl -s --max-time 2 http://localhost:9222/json/version > /dev/null 2>&1; then
            echo "  Chrome CDP: started (took ${i}s)"
            break
        fi
        sleep 1
    done

    if ! curl -s --max-time 2 http://localhost:9222/json/version > /dev/null 2>&1; then
        echo "ERROR: Chrome CDP failed to start after 15s"
        exit 1
    fi
fi

# Refresh cookies
echo ""
echo "Refreshing NotebookLM cookies..."
$PYTHON -c "
import asyncio
from notebooklm import NotebookLMClient

async def refresh():
    client = await NotebookLMClient.from_storage()
    await client.__aenter__()
    print('  Cookies refreshed OK')
    await client.__aexit__(None, None, None)

asyncio.run(refresh())
" 2>&1 || {
    echo "  WARNING: Cookie refresh failed. You may need to run 'notebooklm login'."
}

# Send test question
echo ""
echo "Testing NotebookLM connection..."
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/src"

$PYTHON -c "
import asyncio
import sys
sys.path.insert(0, '$PROJECT_ROOT')

from notebooklm.tools import ask_question, shutdown_client

async def test():
    result = await ask_question('$NOTEBOOK_ID', 'What is Data Commons?')
    if result['success']:
        answer_len = len(result['data'].get('answer', ''))
        citations = result['data'].get('citation_count', 0)
        print(f'  OK — got {answer_len} char response with {citations} citations')
        print(f'  Preview: {result[\"data\"][\"answer\"][:120]}...')
    else:
        print(f'  FAIL — {result[\"error\"]}')
        sys.exit(1)
    await shutdown_client()

asyncio.run(test())
"

echo ""
echo "NotebookLM connection OK — ready for pipeline"
echo "Run with: python src/run_pipeline.py --dataset=<name> --enable-notebooklm"
