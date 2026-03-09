#!/bin/bash
set -e

export PATH="$HOME/.local/bin:$PATH"

echo "=== NotebookLM Viewer — Full Setup ==="
echo ""

# Step 1: Install VNC + browser deps
echo "[1/5] Installing virtual display + VNC..."
sudo apt-get update -qq
sudo apt-get install -y -qq xvfb x11vnc novnc websockify > /dev/null 2>&1
echo "  Done."

# Step 2: Install notebooklm-py + Playwright
echo "[2/5] Installing notebooklm-py + Playwright..."
pip install -q "notebooklm-py[browser]" streamlit nest-asyncio 2>&1 | tail -2
playwright install chromium 2>&1 | tail -2
playwright install-deps chromium 2>/dev/null || true
echo "  Done."

# Step 3: Start virtual display + VNC on port 8080
echo "[3/5] Starting virtual desktop on port 8080..."
pkill -f Xvfb 2>/dev/null || true
pkill -f x11vnc 2>/dev/null || true
pkill -f websockify 2>/dev/null || true
sleep 1
Xvfb :99 -screen 0 1280x720x24 &
sleep 1
export DISPLAY=:99
x11vnc -display :99 -nopw -forever -shared -rfbport 5900 &>/dev/null &
sleep 1
websockify --web /usr/share/novnc 8080 localhost:5900 &>/dev/null &
sleep 1
echo "  Done."

echo ""
echo "=================================================="
echo "  NOW: Click Web Preview (eye icon) -> port 8080"
echo "  You should see a black/gray virtual desktop."
echo "  Then come back HERE and press ENTER to continue."
echo "=================================================="
read -p "Press ENTER when Web Preview is open..."

# Step 4: Run notebooklm login (browser appears in VNC)
echo ""
echo "[4/5] Opening browser for Google login..."
echo "  >>> Switch to the Web Preview tab — sign in there <<<"
echo ""
DISPLAY=:99 notebooklm login

# Verify
if [ ! -f "$HOME/.notebooklm/storage_state.json" ]; then
    echo "ERROR: Login failed — storage_state.json not created."
    exit 1
fi
COOKIE_COUNT=$(python3 -c "import json; print(len(json.load(open('$HOME/.notebooklm/storage_state.json'))['cookies']))" 2>/dev/null || echo "?")
echo "  Login successful! $COOKIE_COUNT cookies saved."

# Step 5: Kill VNC, start Streamlit viewer
echo ""
echo "[5/5] Starting NotebookLM Viewer..."
pkill -f websockify 2>/dev/null || true
pkill -f x11vnc 2>/dev/null || true
pkill -f Xvfb 2>/dev/null || true
sleep 1

# Setup viewer app
mkdir -p ~/notebooklm-viewer
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/setup_cloudshell.sh" ]; then
    bash "$SCRIPT_DIR/setup_cloudshell.sh"
else
    # Inline minimal viewer setup
    cd ~/notebooklm-viewer
    curl -sL "https://raw.githubusercontent.com/nehilsood-cloudsufi/poc-auto-schematization/feature/nehil/notebooklm-agentb/notebooklm/setup_cloudshell.sh" | bash
fi
