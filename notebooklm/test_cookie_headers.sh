#!/bin/bash
set -e

echo "=== NotebookLM Cookie + Browser Headers Test ==="
echo ""

pip install -q httpx 2>/dev/null

STORAGE="$HOME/.notebooklm/storage_state.json"
if [ ! -f "$STORAGE" ]; then
    echo "ERROR: $STORAGE not found. Run cookie extraction first."
    exit 1
fi

python3 << 'PYEOF'
import json, httpx

with open("/home/nehil/.notebooklm/storage_state.json") as f:
    state = json.load(f)

cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in state["cookies"])
print(f"Loaded {len(state['cookies'])} cookies")

headers = {
    "Cookie": cookie_str,
    "User-Agent": "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

print("Making request to notebooklm.google.com...")
r = httpx.get("https://notebooklm.google.com/", headers=headers, follow_redirects=False)
print(f"Status: {r.status_code}")

if r.status_code == 200:
    has_csrf = "SNlM0e" in r.text
    has_session = "FdrFJe" in r.text
    print(f"Has CSRF token: {has_csrf}")
    print(f"Has Session ID: {has_session}")
    if has_csrf and has_session:
        print("")
        print("COOKIES WORK with browser headers!")
        print("We can patch the Streamlit app to use this approach.")
    else:
        print("")
        print("Page loaded but missing tokens.")
elif r.status_code in (301, 302, 303, 307, 308):
    location = r.headers.get("location", "unknown")
    print(f"Redirect: {location[:150]}")
    if "accounts.google.com" in location:
        print("")
        print("Still rejected — cookies are context-bound.")
        print("Cannot use extracted cookies from Cloud Shell.")
    else:
        print(f"Unexpected redirect target.")
else:
    print(f"Unexpected status: {r.status_code}")
PYEOF
