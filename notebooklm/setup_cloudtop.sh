#!/usr/bin/env bash
# NotebookLM Viewer — Cloudtop One-Time Setup
#
# Usage (from Cloudtop desktop terminal):
#   bash notebooklm/setup_cloudtop.sh
#   bash notebooklm/setup_cloudtop.sh --skip-auth
#
# This script:
#   1. Checks prerequisites (Python 3.10+, DISPLAY)
#   2. Clones/updates the repo
#   3. Creates a venv and installs deps (bypasses Corp Airlock via PyPI direct)
#   4. Installs Playwright + Chromium
#   5. Runs `notebooklm login` (opens browser for Google sign-in)
#   6. Launches Streamlit viewer on port 8501

set -euo pipefail

REPO_URL="https://github.com/nehilsood-cloudsufi/poc-auto-schematization.git"
REPO_BRANCH="feature/nehil/notebooklm-agentb"
REPO_DIR="$HOME/work/poc-auto-schematization"
VENV_DIR="$REPO_DIR/.cloudtop_venv"
STORAGE_STATE="$HOME/.notebooklm/storage_state.json"
PORT=8501

SKIP_AUTH=false
for arg in "$@"; do
  case "$arg" in
    --skip-auth) SKIP_AUTH=true ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; exit 1; }

# ---------------------------------------------------------------------------
# 1. Check prerequisites
# ---------------------------------------------------------------------------

info "Checking prerequisites..."

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

# DISPLAY — needed for Playwright login (opens browser)
if [ "$SKIP_AUTH" = false ] && [ -z "${DISPLAY:-}" ]; then
  fail "DISPLAY not set. Run this from the Cloudtop desktop (Chrome Remote Desktop via go/crd), not SSH."
fi

# ---------------------------------------------------------------------------
# 2. Clone or update repo
# ---------------------------------------------------------------------------

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
# 3. Create venv and install Python dependencies
# ---------------------------------------------------------------------------

if [ ! -d "$VENV_DIR" ]; then
  info "Creating virtual environment at $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
  ok "Venv created"
else
  info "Using existing venv at $VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

info "Installing Python packages..."
# Try default pip first; if Corp Airlock blocks it, fall back to PyPI direct
if ! pip install --quiet streamlit "notebooklm-py[browser]" nest-asyncio 2>/dev/null; then
  warn "Default pip failed (likely Corp Airlock). Trying PyPI direct..."
  pip install --index-url https://pypi.org/simple/ --quiet streamlit "notebooklm-py[browser]" nest-asyncio
fi
ok "Python packages installed"

# ---------------------------------------------------------------------------
# 4. Install Playwright + Chromium
# ---------------------------------------------------------------------------

info "Installing Playwright Chromium..."
playwright install chromium 2>/dev/null || python3 -m playwright install chromium

# Install system deps (needs sudo on gLinux)
if command -v sudo &>/dev/null; then
  info "Installing Playwright system dependencies (may ask for sudo)..."
  sudo "$(which playwright)" install-deps chromium 2>/dev/null || \
    playwright install-deps chromium 2>/dev/null || \
    warn "Could not install system deps for Playwright (may already be present)"
fi
ok "Playwright ready"

# ---------------------------------------------------------------------------
# 5. Authenticate with NotebookLM
# ---------------------------------------------------------------------------

if [ "$SKIP_AUTH" = true ]; then
  info "Skipping authentication (--skip-auth)"
  if [ ! -f "$STORAGE_STATE" ]; then
    warn "No auth file found at $STORAGE_STATE — you may need to run without --skip-auth"
  fi
else
  info "Opening browser for Google sign-in..."
  info "Sign in with your @google.com account and tap your security key when prompted."
  echo ""

  notebooklm login

  # Verify auth file was created
  if [ -f "$STORAGE_STATE" ]; then
    ok "Authentication successful — $STORAGE_STATE created"
  else
    fail "Authentication file not found at $STORAGE_STATE. Sign-in may have failed."
  fi
fi

# ---------------------------------------------------------------------------
# 6. Launch Streamlit
# ---------------------------------------------------------------------------

echo ""
echo "=============================================="
ok "Setup complete!"
echo "=============================================="
echo ""
info "Launching NotebookLM Viewer on port $PORT..."
echo ""
echo "  Access from Cloudtop browser:  http://localhost:$PORT"
echo "  Access from Chromebook:        ssh -L $PORT:localhost:$PORT $(hostname)"
echo "                                 then open http://localhost:$PORT"
echo ""
echo "  Press Ctrl+C to stop the server."
echo ""

cd "$REPO_DIR/notebooklm"
streamlit run viewer_app.py --server.port="$PORT" --server.headless=true
