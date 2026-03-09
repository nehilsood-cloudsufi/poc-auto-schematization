#!/bin/bash
set -e

echo "=== NotebookLM OAuth Auth Test ==="
echo ""

# Step 1: Check gcloud auth
echo "[1/3] Checking gcloud auth..."
if ! gcloud auth print-access-token &>/dev/null; then
    echo "  Not authenticated. Running gcloud auth login..."
    echo "  >>> A URL will appear — open it, sign in, paste the code back here <<<"
    echo ""
    gcloud auth login
fi
echo "  Authenticated as: $(gcloud config get-value account 2>/dev/null)"

# Step 2: Install httpx if needed
pip install -q httpx 2>/dev/null

# Step 3: Test OAuth with NotebookLM
echo ""
echo "[2/3] Testing OAuth token with NotebookLM..."
python3 << 'PYEOF'
import subprocess, sys

token = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
print(f"  Token: {token[:20]}...")

import httpx
r = httpx.get("https://notebooklm.google.com/", headers={"Authorization": f"Bearer {token}"}, follow_redirects=False)
print(f"  Status: {r.status_code}")

if r.status_code == 200:
    has_csrf = "SNlM0e" in r.text
    has_session = "FdrFJe" in r.text
    print(f"  Has CSRF token: {has_csrf}")
    print(f"  Has Session ID: {has_session}")
    if has_csrf and has_session:
        print("")
        print("  OAuth auth WORKS!")
        print("  You can use the Streamlit viewer with OAuth tokens.")
    else:
        print("")
        print("  Page loaded but missing tokens. May need different scopes.")
elif r.status_code in (301, 302, 303, 307, 308):
    location = r.headers.get("location", "unknown")
    if "accounts.google.com" in location:
        print(f"  Redirected to login: {location[:100]}...")
        print("")
        print("  OAuth token NOT accepted by NotebookLM.")
        print("  NotebookLM requires browser cookies, not OAuth tokens.")
    else:
        print(f"  Redirected to: {location[:100]}...")
else:
    print(f"  Unexpected status code: {r.status_code}")

PYEOF

echo ""
echo "[3/3] Done."
