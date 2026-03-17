#!/usr/bin/env bash
# NotebookLM Viewer — Single Launch Script for Cloudtop
#
# Does everything in one go:
#   1. Checks prerequisites (Python 3.10+, DISPLAY)
#   2. Clones/updates the repo
#   3. Creates venv + installs deps (skips if already done)
#   4. Launches Chrome with remote debugging (skips if already running)
#   5. Waits for user sign-in (skips if cookies already valid)
#   6. Extracts cookies from Chrome
#   7. Launches Streamlit on port 8501
#
# Usage:
#   bash notebooklm/launch.sh
#   bash notebooklm/launch.sh --fresh     # Force reinstall deps + re-auth

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_URL="https://github.com/nehilsood-cloudsufi/poc-auto-schematization.git"
REPO_BRANCH="feature/nehil/notebooklm-agentb"
REPO_DIR="$HOME/work/poc-auto-schematization"
VENV_DIR="$REPO_DIR/.cloudtop_venv"
STORAGE_DIR="$HOME/.notebooklm"
STORAGE_STATE="$STORAGE_DIR/storage_state.json"
PORT=8501
CDP_PORT=9222
PROFILE_DIR="/tmp/chrome-nlm-debug"

FRESH=false
for arg in "$@"; do
  case "$arg" in
    --fresh) FRESH=true ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[ OK ]\033[0m  $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; exit 1; }

step_num=0
step() { step_num=$((step_num + 1)); echo ""; info "===== Step $step_num: $* ====="; }

# ---------------------------------------------------------------------------
# Step 1: Check prerequisites
# ---------------------------------------------------------------------------

step "Checking prerequisites"

# Python 3.10+
if ! command -v python3 &>/dev/null; then
  fail "python3 not found. Install Python 3.10+ first."
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  fail "Python 3.10+ required (found $PY_VERSION)."
fi
ok "Python $PY_VERSION"

# DISPLAY — needed for Chrome
if [ -z "${DISPLAY:-}" ]; then
  fail "DISPLAY not set. Run from Cloudtop desktop (Chrome Remote Desktop via go/crd), not SSH."
fi
ok "DISPLAY is set ($DISPLAY)"

# ---------------------------------------------------------------------------
# Step 2: Clone or update repo
# ---------------------------------------------------------------------------

step "Setting up repository"

if [ -d "$REPO_DIR/.git" ]; then
  info "Updating existing repo at $REPO_DIR..."
  cd "$REPO_DIR"
  GIT_TERMINAL_PROMPT=0 git fetch origin "$REPO_BRANCH" 2>/dev/null || true
  git checkout "$REPO_BRANCH" 2>/dev/null || true
  GIT_TERMINAL_PROMPT=0 git pull origin "$REPO_BRANCH" 2>/dev/null || true
  ok "Repo updated"
else
  info "Cloning repo to $REPO_DIR..."
  mkdir -p "$(dirname "$REPO_DIR")"
  GIT_TERMINAL_PROMPT=0 git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
  cd "$REPO_DIR"
  ok "Repo cloned"
fi

# ---------------------------------------------------------------------------
# Step 3: Create venv and install deps (skip if already done)
# ---------------------------------------------------------------------------

step "Setting up Python environment"

NEEDS_INSTALL=false

if [ "$FRESH" = true ]; then
  info "Fresh install requested — removing old venv..."
  rm -rf "$VENV_DIR"
  NEEDS_INSTALL=true
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
  NEEDS_INSTALL=true
  # Remove broken venv if directory exists but activate is missing
  rm -rf "$VENV_DIR"
  info "Creating virtual environment at $VENV_DIR..."
  if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
    warn "python3-venv not installed. Installing it now..."
    sudo apt-get update -qq && sudo apt-get install -y -qq "python${PY_VERSION}-venv" 2>/dev/null || \
      sudo apt-get install -y -qq python3-venv 2>/dev/null || \
      fail "Could not install python3-venv. Run: sudo apt install python${PY_VERSION}-venv"
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi
  ok "Venv created"
else
  ok "Venv already exists"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [ "$NEEDS_INSTALL" = true ]; then
  info "Installing Python packages..."
  if ! pip install --quiet streamlit "notebooklm-py[browser]" nest-asyncio 2>/dev/null; then
    warn "Default pip failed (likely Corp Airlock). Trying PyPI direct..."
    pip install --index-url https://pypi.org/simple/ --quiet streamlit "notebooklm-py[browser]" nest-asyncio
  fi
  ok "Python packages installed"
else
  # Quick sanity check — is streamlit importable?
  if python3 -c "import streamlit" 2>/dev/null; then
    ok "Dependencies already installed"
  else
    info "Dependencies missing, installing..."
    if ! pip install --quiet streamlit "notebooklm-py[browser]" nest-asyncio 2>/dev/null; then
      warn "Default pip failed. Trying PyPI direct..."
      pip install --index-url https://pypi.org/simple/ --quiet streamlit "notebooklm-py[browser]" nest-asyncio
    fi
    ok "Python packages installed"
  fi
fi

# ---------------------------------------------------------------------------
# Step 4: Ensure Chrome is running with remote debugging
# ---------------------------------------------------------------------------

step "Starting Chrome with remote debugging"

if curl -s "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
  BROWSER=$(curl -s "http://localhost:$CDP_PORT/json/version" | python3 -c "import sys,json; print(json.load(sys.stdin).get('Browser','Chrome'))" 2>/dev/null || echo "Chrome")
  ok "Chrome already running with CDP on port $CDP_PORT ($BROWSER)"
else
  info "Chrome not running with CDP. Starting it now..."

  # Kill existing Chrome (it blocks --remote-debugging-port if already running)
  # Only kill google-chrome/chromium, NOT Chrome Remote Desktop
  pkill -9 -f "google-chrome" 2>/dev/null || true
  pkill -9 -f "chromium-browser" 2>/dev/null || true
  pkill -9 -f "chromium " 2>/dev/null || true
  sleep 2

  # Verify port is free
  if ss -tlnp 2>/dev/null | grep -q ":$CDP_PORT "; then
    info "Port $CDP_PORT still in use, waiting..."
    sleep 3
    if ss -tlnp 2>/dev/null | grep -q ":$CDP_PORT "; then
      fail "Port $CDP_PORT is blocked. Run: ss -tlnp | grep $CDP_PORT"
    fi
  fi

  # Find Chrome binary
  CHROME_BIN=""
  for candidate in google-chrome google-chrome-stable chromium-browser chromium; do
    if command -v "$candidate" &>/dev/null; then
      CHROME_BIN="$candidate"
      break
    fi
  done
  if [ -z "$CHROME_BIN" ]; then
    fail "No Chrome/Chromium binary found. Install google-chrome or chromium."
  fi

  # Launch Chrome
  info "Using: $CHROME_BIN"
  "$CHROME_BIN" \
    --remote-debugging-port="$CDP_PORT" \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    "https://notebooklm.google.com/" &>/dev/null &

  # Wait for CDP
  info "Waiting for Chrome to start..."
  CHROME_OK=false
  for i in $(seq 1 15); do
    if curl -s "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
      CHROME_OK=true
      break
    fi
    sleep 1
  done

  if [ "$CHROME_OK" = false ]; then
    # Retry with --disable-gpu
    warn "Chrome didn't respond. Retrying with --disable-gpu..."
    "$CHROME_BIN" \
      --remote-debugging-port="$CDP_PORT" \
      --user-data-dir="$PROFILE_DIR" \
      --no-first-run \
      --no-default-browser-check \
      --disable-gpu \
      "https://notebooklm.google.com/" &>/dev/null &
    sleep 5

    if ! curl -s "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
      fail "Chrome failed to start with remote debugging. Try manually:
  $CHROME_BIN --remote-debugging-port=$CDP_PORT --user-data-dir=$PROFILE_DIR https://notebooklm.google.com/"
    fi
  fi

  ok "Chrome running with CDP on port $CDP_PORT"
fi

# ---------------------------------------------------------------------------
# Step 5: Ensure user is signed in + extract cookies
# ---------------------------------------------------------------------------

step "Checking authentication & extracting cookies"

# Try extracting cookies — if key cookies are present, skip sign-in prompt
NEED_SIGNIN=false
if [ "$FRESH" = true ]; then
  NEED_SIGNIN=true
elif [ ! -f "$STORAGE_STATE" ]; then
  NEED_SIGNIN=true
else
  # Try a cookie refresh — check if key auth cookies exist
  info "Refreshing cookies from Chrome..."
  if python3 "$REPO_DIR/notebooklm/refresh_cookies.py" 2>/dev/null; then
    # Check if SID cookie is present (indicates valid sign-in)
    if python3 -c "
import json
state = json.load(open('$STORAGE_STATE'))
names = {c['name'] for c in state.get('cookies', [])}
exit(0 if 'SID' in names else 1)
" 2>/dev/null; then
      ok "Valid auth cookies found"
    else
      NEED_SIGNIN=true
    fi
  else
    NEED_SIGNIN=true
  fi
fi

if [ "$NEED_SIGNIN" = true ]; then
  echo ""
  echo "  =============================================="
  echo "  ACTION REQUIRED: Sign in to NotebookLM"
  echo "  =============================================="
  echo ""
  echo "  A Chrome window should be open on the Cloudtop desktop."
  echo "    1. Sign in with your @google.com account"
  echo "    2. Tap your security key when prompted"
  echo "    3. Wait until NotebookLM loads fully"
  echo ""
  read -rp "  Press ENTER here after you've signed in... "
  echo ""

  info "Extracting cookies from Chrome..."
  if ! python3 "$REPO_DIR/notebooklm/refresh_cookies.py"; then
    fail "Cookie extraction failed. Make sure you're signed into notebooklm.google.com in Chrome."
  fi

  # Verify
  if [ ! -f "$STORAGE_STATE" ]; then
    fail "Auth file not created at $STORAGE_STATE"
  fi
  ok "Authentication successful"
else
  ok "Cookies are fresh"
fi

# ---------------------------------------------------------------------------
# Step 6: Kill any existing Streamlit on the same port
# ---------------------------------------------------------------------------

step "Launching Streamlit"

if ss -tlnp 2>/dev/null | grep -q ":$PORT " || lsof -ti :"$PORT" &>/dev/null; then
  warn "Port $PORT is in use. Stopping existing Streamlit..."
  # Try graceful kill of streamlit on this port
  lsof -ti :"$PORT" 2>/dev/null | xargs kill 2>/dev/null || true
  sleep 2
  # Force kill if still there
  if lsof -ti :"$PORT" &>/dev/null; then
    lsof -ti :"$PORT" 2>/dev/null | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
  ok "Freed port $PORT"
fi

echo ""
echo "  =============================================="
echo "  NotebookLM Viewer is starting!"
echo "  =============================================="
echo ""
echo "  Access from Cloudtop browser:  http://localhost:$PORT"
echo "  Access from Chromebook:        ssh -L $PORT:localhost:$PORT $(hostname)"
echo "                                 then open http://localhost:$PORT"
echo ""
echo "  Cookies auto-refresh from Chrome on each Connect/question."
echo "  Keep Chrome open and signed in!"
echo ""
echo "  Press Ctrl+C to stop the server."
echo ""

cd "$REPO_DIR/notebooklm"
streamlit run viewer_app.py --server.port="$PORT" --server.headless=true
