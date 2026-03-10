#!/usr/bin/env bash
# NotebookLM Viewer — Quick Launch for Cloudtop
#
# Prerequisites:
#   1. Run setup_cloudtop.sh once (installs deps)
#   2. Chrome must be running with:
#      google-chrome --remote-debugging-port=9222 https://notebooklm.google.com/ &
#      (and signed into @google.com)
#
# Usage:
#   bash notebooklm/run_cloudtop.sh

set -euo pipefail

REPO_DIR="$HOME/work/poc-auto-schematization"
VENV_DIR="$REPO_DIR/.cloudtop_venv"
PORT=8501
CDP_PORT=9222

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; exit 1; }

# ---------------------------------------------------------------------------
# 1. Verify setup and activate venv
# ---------------------------------------------------------------------------

if [ ! -f "$VENV_DIR/bin/activate" ]; then
  fail "Venv not found. Run setup_cloudtop.sh first."
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ---------------------------------------------------------------------------
# 2. Ensure Chrome is running with CDP
# ---------------------------------------------------------------------------

if ! curl -s "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
  warn "Chrome not running with remote debugging on port $CDP_PORT."
  echo ""
  echo "  Start Chrome first:"
  echo "    google-chrome --remote-debugging-port=$CDP_PORT https://notebooklm.google.com/ &"
  echo ""
  echo "  Sign in with @google.com in Chrome, then re-run this script."
  echo ""

  # Try to launch Chrome automatically if DISPLAY is set
  if [ -n "${DISPLAY:-}" ]; then
    read -rp "  Or press ENTER to launch Chrome now... " || true
    google-chrome --remote-debugging-port="$CDP_PORT" "https://notebooklm.google.com/" &>/dev/null &
    echo ""
    echo "  Chrome launched. Sign in with @google.com, then press ENTER."
    read -rp "  Press ENTER after sign-in... " || true
  else
    fail "No DISPLAY set. Run from Cloudtop desktop."
  fi
fi

# Verify Chrome is reachable now
if ! curl -s "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
  fail "Chrome still not reachable on port $CDP_PORT."
fi
ok "Chrome running with CDP on port $CDP_PORT"

# ---------------------------------------------------------------------------
# 3. Extract fresh cookies from Chrome
# ---------------------------------------------------------------------------

info "Extracting cookies from Chrome..."
python3 "$REPO_DIR/notebooklm/refresh_cookies.py"
ok "Cookies ready"

# ---------------------------------------------------------------------------
# 4. Launch Streamlit
# ---------------------------------------------------------------------------

echo ""
info "Launching NotebookLM Viewer on port $PORT..."
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
