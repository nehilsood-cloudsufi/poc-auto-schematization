#!/usr/bin/env bash
# Launch Chrome with remote debugging port for cookie extraction.
#
# Usage:
#   bash notebooklm/start_chrome_debug.sh
#
# After Chrome opens, sign in to notebooklm.google.com, then run:
#   bash notebooklm/run_cloudtop.sh

set -euo pipefail

CDP_PORT=9222
PROFILE_DIR="/tmp/chrome-nlm-debug"

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; exit 1; }

# ---------------------------------------------------------------------------
# 1. Check DISPLAY
# ---------------------------------------------------------------------------

if [ -z "${DISPLAY:-}" ]; then
  fail "DISPLAY not set. Run from Cloudtop desktop (Chrome Remote Desktop)."
fi

# ---------------------------------------------------------------------------
# 2. Check if CDP is already working
# ---------------------------------------------------------------------------

if curl -s "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
  ok "Chrome already running with CDP on port $CDP_PORT"
  curl -s "http://localhost:$CDP_PORT/json/version" | python3 -c "import sys,json; print(json.load(sys.stdin).get('Browser','unknown'))" 2>/dev/null || true
  exit 0
fi

# ---------------------------------------------------------------------------
# 3. Kill existing Chrome (it blocks --remote-debugging-port if already running)
# ---------------------------------------------------------------------------

info "Stopping existing Chrome browser processes (not CRD)..."
# Only kill google-chrome/chromium, NOT chrome-remote-desktop or CRD host
pkill -9 -f "google-chrome" 2>/dev/null || true
pkill -9 -f "chromium-browser" 2>/dev/null || true
pkill -9 -f "chromium " 2>/dev/null || true
# Do NOT kill anything with just "chrome" — that kills Chrome Remote Desktop
sleep 2

# Verify port is free
if ss -tlnp 2>/dev/null | grep -q ":$CDP_PORT "; then
  info "Port $CDP_PORT still in use, waiting..."
  sleep 3
  if ss -tlnp 2>/dev/null | grep -q ":$CDP_PORT "; then
    fail "Port $CDP_PORT is blocked by another process. Run: ss -tlnp | grep $CDP_PORT"
  fi
fi

# ---------------------------------------------------------------------------
# 4. Find Chrome binary
# ---------------------------------------------------------------------------

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
info "Using: $CHROME_BIN"

# ---------------------------------------------------------------------------
# 5. Launch Chrome with dedicated debug profile
# ---------------------------------------------------------------------------

info "Launching Chrome with remote debugging on port $CDP_PORT..."
info "Using separate profile at $PROFILE_DIR (won't conflict with your main Chrome)"

"$CHROME_BIN" \
  --remote-debugging-port="$CDP_PORT" \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  "https://notebooklm.google.com/" &>/dev/null &

CHROME_PID=$!

# ---------------------------------------------------------------------------
# 6. Wait for CDP to become available
# ---------------------------------------------------------------------------

info "Waiting for Chrome to start..."
for i in $(seq 1 15); do
  if curl -s "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
    ok "Chrome running with CDP on port $CDP_PORT (PID: $CHROME_PID)"
    curl -s "http://localhost:$CDP_PORT/json/version" | python3 -c "import sys,json; print('  Browser:', json.load(sys.stdin).get('Browser','unknown'))" 2>/dev/null || true
    echo ""
    echo "  Next steps:"
    echo "    1. Sign in to notebooklm.google.com in the Chrome window"
    echo "    2. Then run: bash notebooklm/run_cloudtop.sh"
    echo ""
    echo "  Keep this Chrome open! Cookies are extracted from it automatically."
    exit 0
  fi
  sleep 1
done

# ---------------------------------------------------------------------------
# 7. Debug if Chrome didn't start
# ---------------------------------------------------------------------------

warn "Chrome did not respond on port $CDP_PORT after 15 seconds."
echo ""

if ! kill -0 "$CHROME_PID" 2>/dev/null; then
  echo "  Chrome process died. Trying with --disable-gpu..."
  "$CHROME_BIN" \
    --remote-debugging-port="$CDP_PORT" \
    --user-data-dir="$PROFILE_DIR" \
    --no-first-run \
    --no-default-browser-check \
    --disable-gpu \
    "https://notebooklm.google.com/" &>/dev/null &
  sleep 5

  if curl -s "http://localhost:$CDP_PORT/json/version" &>/dev/null; then
    ok "Chrome running (with --disable-gpu)"
    exit 0
  fi
fi

fail "Chrome failed to start with remote debugging. Try manually:
  $CHROME_BIN --remote-debugging-port=$CDP_PORT --user-data-dir=$PROFILE_DIR https://notebooklm.google.com/
  (run without &>/dev/null to see error output)"
