"""Build storage_state.json from cookies copied from Chrome DevTools.

Usage:
    python3 build_storage_state.py

Then paste your cookie string when prompted.

How to get the cookie string:
    1. On your Chromebook, open Chrome → go to https://notebooklm.google.com/
    2. Sign in (tap security key as needed)
    3. Open DevTools (F12 or Ctrl+Shift+I)
    4. Go to Network tab → click any request to notebooklm.google.com
    5. In the Request Headers section, find "Cookie:" and copy the ENTIRE value
    6. Paste it into this script when prompted
"""

import json
import os
import sys
from pathlib import Path


STORAGE_DIR = Path.home() / ".notebooklm"
STORAGE_STATE = STORAGE_DIR / "storage_state.json"


def parse_cookie_string(cookie_str: str) -> list[dict]:
    """Parse a 'key=value; key2=value2' cookie string into Playwright format."""
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookie = {
            "name": name.strip(),
            "value": value.strip(),
            "domain": ".google.com",
            "path": "/",
            "expires": -1,
            "httpOnly": False,
            "secure": name.strip().startswith("__Secure"),
            "sameSite": "Lax",
        }
        # NotebookLM-specific cookies
        if "notebooklm" in name.lower():
            cookie["domain"] = "notebooklm.google.com"
        cookies.append(cookie)
    return cookies


def build_storage_state(cookie_str: str) -> dict:
    """Build a Playwright-compatible storage_state.json."""
    cookies = parse_cookie_string(cookie_str)
    return {
        "cookies": cookies,
        "origins": [
            {
                "origin": "https://notebooklm.google.com",
                "localStorage": [],
            }
        ],
    }


def main():
    print("=" * 60)
    print("NotebookLM Cookie Extractor")
    print("=" * 60)
    print()
    print("Steps:")
    print("  1. On Chromebook: open https://notebooklm.google.com/")
    print("  2. Sign in with @google.com (tap security key)")
    print("  3. Open DevTools (F12) → Network tab")
    print("  4. Click any request → find 'Cookie:' header")
    print("  5. Copy the entire cookie value")
    print("  6. Paste below (then press Enter twice)")
    print()

    lines = []
    print("Paste cookie string (press Enter twice when done):")
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "" and lines:
            break
        lines.append(line)

    cookie_str = " ".join(lines).strip()
    if not cookie_str:
        print("No cookies provided. Exiting.")
        sys.exit(1)

    # Quick sanity check
    if "SID=" not in cookie_str and "HSID=" not in cookie_str:
        print("Warning: Cookie string doesn't contain SID or HSID.")
        print("Make sure you copied the full Cookie header value.")
        resp = input("Continue anyway? (y/N): ").strip().lower()
        if resp != "y":
            sys.exit(1)

    state = build_storage_state(cookie_str)
    cookie_count = len(state["cookies"])

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STORAGE_STATE, "w") as f:
        json.dump(state, f, indent=2)

    print()
    print(f"Saved {cookie_count} cookies to {STORAGE_STATE}")
    print(f"File size: {STORAGE_STATE.stat().st_size} bytes")
    print()
    print("Now run the viewer:")
    print("  bash notebooklm/run_cloudtop.sh")


if __name__ == "__main__":
    main()
