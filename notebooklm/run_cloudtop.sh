#!/usr/bin/env bash
# NotebookLM Viewer — Quick Launch for Cloudtop
#
# Usage:
#   bash notebooklm/run_cloudtop.sh
#   bash notebooklm/run_cloudtop.sh --reauth
#
# Prerequisites: run setup_cloudtop.sh first (one-time).

set -euo pipefail

REPO_DIR="$HOME/work/poc-auto-schematization"
VENV_DIR="$REPO_DIR/.cloudtop_venv"
STORAGE_STATE="$HOME/.notebooklm/storage_state.json"
PORT=8501

REAUTH=false
for arg in "$@"; do
  case "$arg" in
    --reauth) REAUTH=true ;;
  esac
done

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; exit 1; }

# ---------------------------------------------------------------------------
# 1. Verify setup and activate venv
# ---------------------------------------------------------------------------

if [ ! -d "$REPO_DIR/notebooklm" ]; then
  fail "Repo not found at $REPO_DIR. Run setup_cloudtop.sh first."
fi

if [ ! -d "$VENV_DIR" ]; then
  fail "Venv not found at $VENV_DIR. Run setup_cloudtop.sh first."
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ---------------------------------------------------------------------------
# 2. Re-authenticate if requested
# ---------------------------------------------------------------------------

if [ "$REAUTH" = true ]; then
  if [ -z "${DISPLAY:-}" ]; then
    fail "DISPLAY not set. Run this from the Cloudtop desktop (Chrome Remote Desktop) for re-auth."
  fi
  info "Re-authenticating — extract fresh cookies from Chromebook..."
  source "$VENV_DIR/bin/activate"
  python3 "$REPO_DIR/notebooklm/build_storage_state.py"
  ok "Re-authentication complete"
fi

# ---------------------------------------------------------------------------
# 3. Check auth file
# ---------------------------------------------------------------------------

if [ ! -f "$STORAGE_STATE" ]; then
  fail "No auth file at $STORAGE_STATE. Run setup_cloudtop.sh first, or use --reauth."
fi
ok "Auth file found ($(stat -c '%y' "$STORAGE_STATE" 2>/dev/null || stat -f '%Sm' "$STORAGE_STATE" 2>/dev/null || echo 'unknown date'))"

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
echo "  Press Ctrl+C to stop the server."
echo ""

cd "$REPO_DIR/notebooklm"
streamlit run viewer_app.py --server.port="$PORT" --server.headless=true
