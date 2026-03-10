#!/usr/bin/env bash
# NotebookLM Viewer — Quick Launch for Cloudtop
#
# Usage:
#   bash notebooklm/run_cloudtop.sh
#   bash notebooklm/run_cloudtop.sh --reauth
#
# Auto-refreshes cookies from the running Chrome instance before launch.
# Prerequisites: run setup_cloudtop.sh first (one-time).

set -euo pipefail

REPO_DIR="$HOME/work/poc-auto-schematization"
VENV_DIR="$REPO_DIR/.cloudtop_venv"
STORAGE_STATE="$HOME/.notebooklm/storage_state.json"
PORT=8501
CDP_PORT=9222

REAUTH=false
for arg in "$@"; do
  case "$arg" in
    --reauth) REAUTH=true ;;
  esac
done

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; exit 1; }

# ---------------------------------------------------------------------------
# 1. Verify setup and activate venv
# ---------------------------------------------------------------------------

if [ ! -d "$REPO_DIR/notebooklm" ]; then
  fail "Repo not found at $REPO_DIR. Run setup_cloudtop.sh first."
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
  fail "Venv not found at $VENV_DIR. Run setup_cloudtop.sh first."
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ---------------------------------------------------------------------------
# 2. Re-authenticate if requested (opens Chrome for sign-in)
# ---------------------------------------------------------------------------

if [ "$REAUTH" = true ]; then
  if [ -z "${DISPLAY:-}" ]; then
    fail "DISPLAY not set. Run this from the Cloudtop desktop (Chrome Remote Desktop) for re-auth."
  fi

  # Launch Chrome if not already running
  if ! curl -s "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
    info "Launching Chrome with remote debugging..."
    google-chrome --remote-debugging-port="$CDP_PORT" "https://notebooklm.google.com/" &>/dev/null &
    sleep 3
  else
    info "Chrome already running. Opening NotebookLM tab..."
    # Just tell user to sign in in the existing Chrome
  fi

  echo ""
  info "Sign in to NotebookLM in the Chrome window, then press ENTER."
  read -rp "  Press ENTER after sign-in... "
  echo ""
fi

# ---------------------------------------------------------------------------
# 3. Auto-refresh cookies from Chrome (if running)
# ---------------------------------------------------------------------------

if curl -s "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
  info "Refreshing cookies from Chrome..."
  python3 "$REPO_DIR/notebooklm/refresh_cookies.py" && ok "Cookies refreshed" || warn "Cookie refresh failed"
else
  warn "Chrome not running (no CDP on port $CDP_PORT). Using existing cookies."
fi

# ---------------------------------------------------------------------------
# 4. Check auth file
# ---------------------------------------------------------------------------

if [ ! -f "$STORAGE_STATE" ]; then
  fail "No auth file at $STORAGE_STATE. Run setup_cloudtop.sh first, or use --reauth."
fi
ok "Auth file present"

# ---------------------------------------------------------------------------
# 5. Launch Streamlit
# ---------------------------------------------------------------------------

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
