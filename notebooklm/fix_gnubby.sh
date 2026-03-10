#!/usr/bin/env bash
# Fix gnubby "Error: 512" on Cloudtop
#
# Usage:
#   bash notebooklm/fix_gnubby.sh
#
# After this succeeds, run:
#   bash notebooklm/setup_cloudtop.sh

set -euo pipefail

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; exit 1; }

try_gcert() {
  info "Testing gcert..."
  if gcert 2>&1; then
    ok "gcert succeeded!"
    return 0
  fi
  return 1
}

# ---------------------------------------------------------------------------
# Step 1: Kill all gnubby processes and restart
# ---------------------------------------------------------------------------

info "Step 1: Restarting gnubby daemon..."
pkill -9 gnubbyd 2>/dev/null || true
pkill -9 gnubby 2>/dev/null || true
sleep 2

if command -v gnubbyd &>/dev/null; then
  gnubbyd &>/dev/null &
  sleep 1
  ok "gnubbyd restarted"
fi

if try_gcert; then exit 0; fi

# ---------------------------------------------------------------------------
# Step 2: Restart via systemctl
# ---------------------------------------------------------------------------

info "Step 2: Trying systemctl restart..."
if command -v systemctl &>/dev/null; then
  sudo systemctl restart gnubbyd 2>/dev/null || \
    sudo systemctl restart gnubby 2>/dev/null || \
    warn "systemctl restart failed (may not be a systemd service)"
  sleep 2
fi

if try_gcert; then exit 0; fi

# ---------------------------------------------------------------------------
# Step 3: Reset SSH agent
# ---------------------------------------------------------------------------

info "Step 3: Resetting SSH agent..."
pkill -9 ssh-agent 2>/dev/null || true
eval "$(ssh-agent -s)"
sleep 1

if try_gcert; then exit 0; fi

# ---------------------------------------------------------------------------
# Step 4: Try gcert --noforward
# ---------------------------------------------------------------------------

info "Step 4: Trying gcert --noforward..."
if gcert --noforward 2>&1; then
  ok "gcert --noforward succeeded!"
  exit 0
fi

# ---------------------------------------------------------------------------
# Step 5: Full reset — kill everything, wait, restart
# ---------------------------------------------------------------------------

info "Step 5: Full reset — killing all gnubby/ssh-agent processes..."
pkill -9 gnubbyd 2>/dev/null || true
pkill -9 gnubby 2>/dev/null || true
pkill -9 ssh-agent 2>/dev/null || true
sleep 5

eval "$(ssh-agent -s)"
if command -v gnubbyd &>/dev/null; then
  gnubbyd &>/dev/null &
fi
sleep 3

if try_gcert; then exit 0; fi

# ---------------------------------------------------------------------------
# None worked
# ---------------------------------------------------------------------------

echo ""
fail "All fixes failed. Try:
  1. Disconnect from Chrome Remote Desktop and reconnect
  2. Then run: bash notebooklm/fix_gnubby.sh
  3. If still failing, check go/gcert-panic for outages
  4. Last resort: go/emergency-credentials"
