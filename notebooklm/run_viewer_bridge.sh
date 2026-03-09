#!/bin/bash
set -e

export PATH="$HOME/.local/bin:$PATH"

echo "=== NotebookLM Viewer (Bridge Mode) ==="
echo ""

# Setup
mkdir -p ~/notebooklm-viewer
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Copy files
cp "$SCRIPT_DIR/bridge_server.py" ~/notebooklm-viewer/
cp "$SCRIPT_DIR/viewer_app_bridge.py" ~/notebooklm-viewer/
mkdir -p ~/notebooklm-viewer/.streamlit
cat > ~/notebooklm-viewer/.streamlit/config.toml << 'EOF'
[server]
headless = true
enableCORS = false
enableXsrfProtection = false
[browser]
gatherUsageStats = false
EOF

cd ~/notebooklm-viewer

# Install deps
echo "[1/3] Installing dependencies..."
pip install -q streamlit requests 2>&1 | tail -2

# Start bridge server in background
echo "[2/3] Starting bridge relay on port 8081..."
python3 bridge_server.py &
BRIDGE_PID=$!
sleep 1

# Cleanup on exit
trap "kill $BRIDGE_PID 2>/dev/null" EXIT

echo "[3/3] Starting Streamlit on port 8080..."
echo ""
echo "=========================================="
echo "  Open Web Preview (eye icon) → port 8080"
echo "=========================================="
echo ""

streamlit run viewer_app_bridge.py \
    --server.port=8080 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false \
    --server.fileWatcherType=none
