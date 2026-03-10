#!/usr/bin/env bash
# NotebookLM Viewer — Cloudtop One-Time Setup
#
# Usage (from Cloudtop desktop terminal):
#   curl -sL <raw-url>/notebooklm/setup_cloudtop.sh | bash
#   curl -sL <raw-url>/notebooklm/setup_cloudtop.sh | bash -s -- --skip-auth
#
# This script:
#   1. Checks prerequisites (Python 3.10+, DISPLAY)
#   2. Clones/updates the repo
#   3. Installs Python deps + Playwright
#   4. Runs `notebooklm login` (opens browser for Google sign-in)
#   5. Launches Streamlit viewer on port 8501

set -euo pipefail

REPO_URL="https://github.com/nehilsood-cloudsufi/poc-auto-schematization.git"
REPO_BRANCH="feature/nehil/notebooklm-agentb"
REPO_DIR="$HOME/work/poc-auto-schematization"
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
  git fetch origin "$REPO_BRANCH" 2>/dev/null || true
  git checkout "$REPO_BRANCH" 2>/dev/null || true
  git pull origin "$REPO_BRANCH" 2>/dev/null || true
  ok "Repo updated"
else
  info "Cloning repo to $REPO_DIR..."
  mkdir -p "$(dirname "$REPO_DIR")"
  git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
  cd "$REPO_DIR"
  ok "Repo cloned"
fi

# ---------------------------------------------------------------------------
# 3. Install Python dependencies
# ---------------------------------------------------------------------------

info "Installing Python packages..."
python3 -m pip install --user --quiet streamlit "notebooklm-py[browser]" nest-asyncio

# Ensure ~/.local/bin is on PATH
LOCAL_BIN="$HOME/.local/bin"
if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
  export PATH="$LOCAL_BIN:$PATH"
  # Persist for future shells
  if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    info "Added ~/.local/bin to PATH in ~/.bashrc"
  fi
fi
ok "Python packages installed"

# ---------------------------------------------------------------------------
# 4. Install Playwright + Chromium
# ---------------------------------------------------------------------------

info "Installing Playwright Chromium..."
python3 -m playwright install chromium 2>/dev/null || playwright install chromium
if command -v sudo &>/dev/null; then
  sudo python3 -m playwright install-deps chromium 2>/dev/null || \
    python3 -m playwright install-deps chromium 2>/dev/null || \
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

  if command -v notebooklm &>/dev/null; then
    notebooklm login
  else
    python3 -m notebooklm login 2>/dev/null || "$LOCAL_BIN/notebooklm" login
  fi

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
python3 -m streamlit run viewer_app.py --server.port="$PORT" --server.headless=true
