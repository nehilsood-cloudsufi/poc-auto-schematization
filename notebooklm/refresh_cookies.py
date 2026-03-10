"""Auto-extract cookies from a running Chrome instance via Chrome DevTools Protocol.

Requires Chrome to be running with --remote-debugging-port=9222.
Connects via CDP, extracts notebooklm.google.com cookies, and saves
to ~/.notebooklm/storage_state.json.

Usage:
    python3 refresh_cookies.py              # Extract and save
    python3 refresh_cookies.py --check      # Just check if Chrome is reachable
"""

import json
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

CDP_URL = "http://localhost:9222"
STORAGE_DIR = Path.home() / ".notebooklm"
STORAGE_STATE = STORAGE_DIR / "storage_state.json"


def check_chrome():
    """Check if Chrome with debugging is reachable."""
    try:
        resp = urlopen(f"{CDP_URL}/json/version", timeout=3)
        info = json.loads(resp.read())
        return True, info.get("Browser", "Chrome")
    except (URLError, OSError):
        return False, None


def get_ws_url():
    """Get the WebSocket URL of the first Chrome tab."""
    try:
        resp = urlopen(f"{CDP_URL}/json", timeout=3)
        tabs = json.loads(resp.read())
        for tab in tabs:
            if tab.get("type") == "page":
                return tab.get("webSocketDebuggerUrl")
    except (URLError, OSError):
        pass
    return None


def extract_cookies_via_cdp():
    """Extract cookies from Chrome via CDP using websocket."""
    import websocket  # pip install websocket-client

    ws_url = get_ws_url()
    if not ws_url:
        print("ERROR: Could not get WebSocket URL from Chrome.")
        return None

    ws = websocket.create_connection(ws_url)

    # Request all cookies for notebooklm.google.com
    ws.send(json.dumps({
        "id": 1,
        "method": "Network.getCookies",
        "params": {"urls": ["https://notebooklm.google.com/"]}
    }))

    resp = json.loads(ws.recv())
    ws.close()

    if "result" not in resp or "cookies" not in resp["result"]:
        print("ERROR: Unexpected CDP response:", resp)
        return None

    return resp["result"]["cookies"]


def cdp_cookies_to_storage_state(cdp_cookies: list) -> dict:
    """Convert CDP cookie format to Playwright storage_state format."""
    pw_cookies = []
    for c in cdp_cookies:
        pw_cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain", ".google.com"),
            "path": c.get("path", "/"),
            "expires": c.get("expires", -1),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
            "sameSite": c.get("sameSite", "Lax"),
        }
        pw_cookies.append(pw_cookie)

    return {
        "cookies": pw_cookies,
        "origins": [
            {
                "origin": "https://notebooklm.google.com",
                "localStorage": [],
            }
        ],
    }


def main():
    check_only = "--check" in sys.argv

    reachable, browser = check_chrome()
    if not reachable:
        print("Chrome is not running with remote debugging.")
        print("")
        print("Start it with:")
        print("  google-chrome --remote-debugging-port=9222 https://notebooklm.google.com &")
        print("")
        print("Then sign in with your @google.com account (tap security key).")
        print("Keep Chrome open, then re-run this script.")
        sys.exit(1)

    print(f"Connected to: {browser}")

    if check_only:
        print("Chrome is reachable.")
        sys.exit(0)

    try:
        cdp_cookies = extract_cookies_via_cdp()
    except ImportError:
        print("ERROR: websocket-client not installed. Run: pip install websocket-client")
        sys.exit(1)

    if not cdp_cookies:
        print("No cookies found. Make sure you're signed into notebooklm.google.com in Chrome.")
        sys.exit(1)

    state = cdp_cookies_to_storage_state(cdp_cookies)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STORAGE_STATE, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Saved {len(cdp_cookies)} cookies to {STORAGE_STATE}")

    # Check for key cookies
    names = {c["name"] for c in cdp_cookies}
    for key in ("SID", "HSID", "SSID"):
        if key in names:
            print(f"  {key}: present")
        else:
            print(f"  {key}: MISSING (may cause auth failure)")


if __name__ == "__main__":
    main()
