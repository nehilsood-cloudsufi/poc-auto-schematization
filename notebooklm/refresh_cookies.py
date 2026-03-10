"""Auto-extract cookies from a running Chrome instance via Chrome DevTools Protocol.

Requires Chrome to be running with --remote-debugging-port=9222.
Connects via CDP WebSocket, extracts notebooklm.google.com cookies, and saves
to ~/.notebooklm/storage_state.json.

Uses ONLY Python stdlib — no external dependencies.

Usage:
    python3 refresh_cookies.py              # Extract and save
    python3 refresh_cookies.py --check      # Just check if Chrome is reachable
"""

import hashlib
import http.client
import json
import os
import socket
import struct
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


# ---------------------------------------------------------------------------
# Minimal WebSocket client (stdlib only, no masking needed for local CDP)
# ---------------------------------------------------------------------------

def _ws_connect(url: str) -> socket.socket:
    """Open a WebSocket connection to a ws:// URL. Returns raw socket."""
    # Parse ws://host:port/path
    assert url.startswith("ws://"), f"Expected ws:// URL, got {url}"
    rest = url[5:]
    slash = rest.find("/")
    host_port = rest[:slash] if slash >= 0 else rest
    path = rest[slash:] if slash >= 0 else "/"
    host, port_str = host_port.split(":")
    port = int(port_str)

    sock = socket.create_connection((host, port), timeout=10)

    # WebSocket handshake
    key = "dGhlIHNhbXBsZSBub25jZQ=="  # fixed nonce, fine for local CDP
    handshake = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"\r\n"
    )
    sock.sendall(handshake.encode())

    # Read response headers
    resp = b""
    while b"\r\n\r\n" not in resp:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("WebSocket handshake failed: connection closed")
        resp += chunk

    if b"101" not in resp.split(b"\r\n")[0]:
        raise ConnectionError(f"WebSocket handshake failed: {resp.decode(errors='replace')}")

    return sock


def _ws_send(sock: socket.socket, data: str):
    """Send a WebSocket text frame (masked, as required by RFC 6455)."""
    payload = data.encode("utf-8")
    # Frame: FIN=1, opcode=1 (text), MASK=1
    frame = bytearray()
    frame.append(0x81)  # FIN + text opcode

    length = len(payload)
    if length < 126:
        frame.append(0x80 | length)  # MASK bit set
    elif length < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack("!H", length))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack("!Q", length))

    # Masking key (fixed, fine for local)
    mask = b"\x00\x00\x00\x00"
    frame.extend(mask)
    frame.extend(payload)  # mask is all zeros so payload unchanged
    sock.sendall(bytes(frame))


def _ws_recv(sock: socket.socket) -> str:
    """Receive a WebSocket text frame."""
    # Read frame header
    header = b""
    while len(header) < 2:
        header += sock.recv(2 - len(header))

    b1, b2 = header[0], header[1]
    masked = b2 & 0x80
    length = b2 & 0x7F

    if length == 126:
        raw = b""
        while len(raw) < 2:
            raw += sock.recv(2 - len(raw))
        length = struct.unpack("!H", raw)[0]
    elif length == 127:
        raw = b""
        while len(raw) < 8:
            raw += sock.recv(8 - len(raw))
        length = struct.unpack("!Q", raw)[0]

    if masked:
        mask = b""
        while len(mask) < 4:
            mask += sock.recv(4 - len(mask))

    # Read payload
    payload = b""
    while len(payload) < length:
        chunk = sock.recv(min(65536, length - len(payload)))
        if not chunk:
            break
        payload += chunk

    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

    return payload.decode("utf-8")


# ---------------------------------------------------------------------------
# CDP cookie extraction
# ---------------------------------------------------------------------------

def extract_cookies_via_cdp():
    """Extract cookies from Chrome via CDP WebSocket (stdlib only)."""
    ws_url = get_ws_url()
    if not ws_url:
        print("ERROR: Could not get WebSocket URL from Chrome.")
        return None

    sock = _ws_connect(ws_url)

    # Request all cookies for notebooklm.google.com
    _ws_send(sock, json.dumps({
        "id": 1,
        "method": "Network.getCookies",
        "params": {"urls": ["https://notebooklm.google.com/"]}
    }))

    resp = json.loads(_ws_recv(sock))
    sock.close()

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
        print("Run: bash notebooklm/start_chrome_debug.sh")
        sys.exit(1)

    print(f"Connected to: {browser}")

    if check_only:
        print("Chrome is reachable.")
        sys.exit(0)

    cdp_cookies = extract_cookies_via_cdp()

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
