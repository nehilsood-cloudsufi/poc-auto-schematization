#!/usr/bin/env bash
# NotebookLM Viewer — Quick Launch for Cloudtop
#
# Usage:
#   curl -sL <raw-url>/notebooklm/run_cloudtop.sh | bash
#   curl -sL <raw-url>/notebooklm/run_cloudtop.sh | bash -s -- --reauth
#
# Prerequisites: run setup_cloudtop.sh first (one-time).

set -euo pipefail

REPO_DIR="$HOME/work/poc-auto-schematization"
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

# Ensure ~/.local/bin is on PATH
export PATH="$HOME/.local/bin:$PATH"

# ---------------------------------------------------------------------------
# 1. Verify setup
# ---------------------------------------------------------------------------

if [ ! -d "$REPO_DIR/notebooklm" ]; then
  fail "Repo not found at $REPO_DIR. Run setup_cloudtop.sh first."
fi

# ---------------------------------------------------------------------------
# 2. Re-authenticate if requested
# ---------------------------------------------------------------------------

if [ "$REAUTH" = true ]; then
  if [ -z "${DISPLAY:-}" ]; then
    fail "DISPLAY not set. Run this from the Cloudtop desktop (Chrome Remote Desktop) for re-auth."
  fi
  info "Re-authenticating — sign in and tap your security key..."
  if command -v notebooklm &>/dev/null; then
    notebooklm login
  else
    python3 -m notebooklm login
  fi
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
python3 -m streamlit run viewer_app.py --server.port="$PORT" --server.headless=true
