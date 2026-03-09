# NotebookLM Viewer — Authentication Investigation Report

**Date:** 2026-03-09
**Author:** Nehil Sood
**Environment:** Managed Google Chromebook (@google.com account), Cloud Shell, cloudsufi-ai / datcom-infosys-dev GCP projects

---

## Objective

Build a Streamlit chat app that connects to a view-only NotebookLM notebook, deployed to Cloud Run or accessible via Cloud Shell. The app uses `notebooklm-py` (Python library) which authenticates via browser cookies stored in `storage_state.json`.

---

## Constraints

| Constraint | Detail |
|-----------|--------|
| Device | Managed Google Chromebook — no admin access |
| Linux (Crostini) | Blocked by Google corporate device policy |
| Authentication | @google.com account with **hardware security key** (YubiKey/Titan) required for 2FA |
| NotebookLM API | No public API — uses internal Google batchexecute RPC endpoints, requires browser session cookies |
| `notebooklm-py` auth | Server-side HTTP calls using cookies from `~/.notebooklm/storage_state.json` |

---

## Attempts

### Attempt 1: Deploy to Cloud Run (cloudsufi-ai) with manually extracted cookies

**Approach:**
1. Opened NotebookLM in Chrome on Chromebook
2. Extracted cookies from DevTools → Network tab → Request Headers → Cookie header (24 cookies including SID, HSID, SSID, APISID, SAPISID, __Secure-* variants, OSID, __Secure-GSSO_UberProxy)
3. Built `storage_state.json` from extracted cookies using a Python script on Cloud Shell
4. Stored as GCP Secret (`NOTEBOOKLM_STORAGE_STATE`) in cloudsufi-ai
5. Deployed Streamlit + notebooklm-py to Cloud Run with Playwright/Chromium in the container

**Result:** FAILED

**Error:**
```
ValueError: Authentication expired or invalid. Redirected to:
https://accounts.google.com/v3/signin/identifier?continue=https%3A%2F%2Fnotebooklm.google.com%2F...
```

**Root cause:** Google session cookies (especially `__Secure-GSSO_UberProxy`, the Google corporate SSO cookie) are **context-bound** — they are validated against the network/device context where they were created. Cloud Run's public IP is not on the Google corporate network, so Google rejects the cookies and redirects to the login page.

---

### Attempt 2: Run Streamlit on Cloud Shell (inside Google's network)

**Approach:**
1. Same manually extracted cookies as Attempt 1
2. Ran the Streamlit app directly on Cloud Shell instead of Cloud Run
3. Accessed via Cloud Shell Web Preview (port 8080)
4. Theory: Cloud Shell is inside Google's infrastructure, so cookies might work

**Result:** FAILED

**Error:** Same `ValueError: Authentication expired or invalid. Redirected to login` as Attempt 1.

**Root cause:** Cloud Shell's egress IP is still not recognized as part of the corporate network context where the cookies were created. The `GSSO_UberProxy` cookie validation failed.

---

### Attempt 3: Add browser-like headers to cookie requests

**Approach:**
1. Hypothesized that `notebooklm-py` (which uses `httpx`) might be missing browser headers that Google checks
2. Made direct HTTP requests from Cloud Shell with full browser headers:
   - `User-Agent` matching Chrome on ChromeOS
   - `Sec-Fetch-Dest`, `Sec-Fetch-Mode`, `Sec-Fetch-Site`, `Sec-Fetch-User`
   - `Accept`, `Accept-Language`
3. Sent the 24 extracted cookies with these headers

**Result:** FAILED

**Error:**
```
Status: 302
Redirect: https://accounts.google.com/ServiceLogin?passive=1209600&osid=1&continue=https://notebooklm.google.com/
```

**Root cause:** Google's cookie validation is not based on User-Agent or Sec-Fetch headers. The session cookies are fundamentally bound to the originating device/network context. Browser-like headers do not bypass this validation.

---

### Attempt 4: Playwright login via noVNC on Cloud Shell

**Approach:**
1. Installed Xvfb (virtual display), x11vnc, noVNC, websockify on Cloud Shell
2. Started a virtual desktop accessible via Cloud Shell Web Preview
3. Ran `notebooklm login` (Playwright) which opens Chromium in the virtual desktop
4. User would interact with the browser through noVNC to complete Google sign-in with the security key

**Result:** FAILED

**Reason:** The hardware security key (YubiKey/Titan) requires **USB HID access** to the physical device. noVNC is a screen-sharing protocol — it cannot forward USB device access. The WebAuthn/FIDO2 security key challenge cannot be completed through a VNC session.

---

### Attempt 5: OAuth token authentication (gcloud auth)

**Approach:**
1. Authenticated to Google on Cloud Shell using `gcloud auth login` (which opens a browser URL — security key works here since it's in the actual browser)
2. Retrieved an OAuth access token via `gcloud auth print-access-token`
3. Made HTTP request to `https://notebooklm.google.com/` with `Authorization: Bearer <token>` header

**Result:** FAILED

**Error:**
```
Status: 302
Redirect: https://accounts.google.com/ServiceLogin?passive=1209600&osid=1&continue=https://notebooklm.google.com/
```

**Root cause:** NotebookLM does **not accept OAuth bearer tokens**. It exclusively requires browser session cookies for authentication. Unlike most Google Cloud APIs which support OAuth, NotebookLM's internal batchexecute RPC endpoints only validate cookie-based sessions.

---

### Attempt 6 (In Progress): Browser Bridge Architecture

**Approach:**
1. Streamlit chat UI runs on Cloud Shell (port 8080, accessed via Web Preview)
2. A bridge relay server runs on Cloud Shell (port 8081)
3. A JavaScript snippet is injected into the NotebookLM page (via DevTools Console) on the Chromebook
4. The JS snippet polls the bridge relay for questions from Streamlit
5. When a question arrives, the JS makes a `fetch()` call to NotebookLM's internal API — this is a **same-origin request** from `notebooklm.google.com`, so the browser automatically includes all authenticated cookies
6. The JS sends the API response back through the bridge relay to Streamlit

**Status:** Not yet tested. This approach should work in theory because the actual API calls are made from the authenticated browser context, not from Cloud Shell.

**Risk:** Cloud Shell Web Preview may add authentication layers that complicate cross-tab communication between the NotebookLM tab and the bridge relay.

---

## Summary: Why It's Not Working

### The Core Problem

NotebookLM has **no public API**. The `notebooklm-py` library works by reverse-engineering NotebookLM's internal Google batchexecute RPC endpoints, which require **browser session cookies** for authentication.

### Why Cookies Don't Work Remotely

Google's authentication system for @google.com (corporate) accounts uses **UberProxy/GSSO** — an internal single-sign-on system that binds session cookies to the device and network context where the authentication occurred. Specifically:

1. **`__Secure-GSSO_UberProxy`** — This cookie is the corporate SSO token. It is validated server-side against the originating context (IP, network, device fingerprint).
2. **`SID`, `HSID`, `SSID`** — These core Google session cookies are also context-validated for corporate accounts.
3. **Context binding** — When these cookies are used from a different IP address or network (Cloud Shell, Cloud Run, or any external server), Google's authentication backend detects the mismatch and forces a re-authentication redirect.

This is a **security feature by design** — it prevents session hijacking by ensuring stolen cookies cannot be replayed from a different machine.

### Why Alternative Auth Methods Don't Work

| Method | Why it fails |
|--------|-------------|
| OAuth tokens | NotebookLM doesn't accept OAuth — only browser cookies |
| Manually extracted cookies | Context-bound to the originating device/network |
| Playwright login from Cloud Shell | Requires hardware security key, which can't be forwarded through VNC |
| Crostini (Linux on Chromebook) | Blocked by corporate device management policy |

### What Would Work

| Solution | Feasibility |
|----------|-------------|
| **Browser bridge** (JS in NotebookLM tab relays API calls) | Possible — being tested |
| **Playwright login on a machine with the security key and Python** | Requires a gLinux workstation or unmanaged laptop with Python + USB access |
| **Google providing a public NotebookLM API with OAuth support** | Not currently available |
| **Enabling Crostini on the Chromebook** | Requires IT policy change |
| **Using a non-corporate Google account** (no GSSO/UberProxy) | Would bypass context binding, but may not have access to the shared notebook |

---

## Files Created

| File | Purpose | Status |
|------|---------|--------|
| `viewer_app.py` | Streamlit chat app (direct notebooklm-py auth) | Works locally, fails on Cloud Shell/Cloud Run due to auth |
| `Dockerfile.viewer` | Container for Cloud Run deployment | Built and deployed successfully |
| `deploy_viewer.sh` | Cloud Run deploy script | Deployed to cloudsufi-ai successfully |
| `startup_viewer.sh` | Container entrypoint | Works |
| `setup_cloudshell.sh` | Cloud Shell one-command setup | Works (app loads, auth fails) |
| `login_and_run.sh` | noVNC + Playwright login script | VNC works, security key blocks login |
| `test_oauth_auth.sh` | OAuth token test | Confirmed NotebookLM rejects OAuth |
| `test_cookie_headers.sh` | Cookie + browser headers test | Confirmed cookies are context-bound |
| `bridge_server.py` | Bridge relay server | Created, not yet tested |
| `viewer_app_bridge.py` | Streamlit app (bridge mode) | Created, not yet tested |
| `run_viewer_bridge.sh` | Bridge mode launcher | Created, not yet tested |
