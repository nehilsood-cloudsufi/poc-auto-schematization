# Next Phase Development — NotebookLM Viewer

## What We Built

A **Streamlit chat application** that provides a conversational interface to Google NotebookLM notebooks. Users paste a notebook URL, connect, and ask questions — the app queries NotebookLM and returns answers with source citations.

**Stack:** Streamlit + [notebooklm-py](https://github.com/teng-lin/notebooklm-py) (reverse-engineered Python client) + Chrome DevTools Protocol for authentication.

### Current Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Cloudtop (gLinux VM)                  │
│                                                         │
│  ┌──────────────┐    CDP (port 9222)    ┌────────────┐  │
│  │ Chrome       │◄─────────────────────►│ Cookie     │  │
│  │ (signed in   │  extract cookies      │ Refresh    │  │
│  │  to Google)  │  before each request  │ Script     │  │
│  └──────────────┘                       └─────┬──────┘  │
│                                               │         │
│                                         ┌─────▼──────┐  │
│                                         │ Streamlit  │  │
│                                         │ Viewer App │  │
│                                         │ (port 8501)│  │
│                                         └─────┬──────┘  │
│                                               │         │
│                                    httpx calls with     │
│                                    extracted cookies     │
│                                               │         │
└───────────────────────────────────────────────┼─────────┘
                                                │
                                                ▼
                                    notebooklm.google.com
                                    (internal batchexecute RPC)
```

### How Authentication Works (and Why It's Complex)

NotebookLM has **no public API**. The `notebooklm-py` library works by reverse-engineering NotebookLM's internal Google `batchexecute` RPC endpoints, which require **browser session cookies** for authentication.

**The cookie refresh cycle:**

1. Chrome runs on Cloudtop with `--remote-debugging-port=9222`, signed into @google.com
2. Before every API call, the app connects to Chrome via the **Chrome DevTools Protocol** (CDP)
3. It extracts fresh session cookies (`SID`, `HSID`, `SSID`, `__Secure-GSSO_UberProxy`, etc.)
4. These cookies are saved to `~/.notebooklm/storage_state.json`
5. `notebooklm-py` reads this file and uses the cookies for its HTTP requests
6. This cycle repeats for **every single question** because cookies expire within 20–60 minutes

---

## Security Limitations

### 1. Google Session Cookies Are Context-Bound

Google's authentication system for @google.com (corporate) accounts uses **UberProxy/GSSO** — an internal single-sign-on system that binds session cookies to the **device and network context** where authentication occurred.

| Cookie | Purpose | Binding |
|--------|---------|---------|
| `__Secure-GSSO_UberProxy` | Corporate SSO token | Validated against originating IP/network/device |
| `SID`, `HSID`, `SSID` | Core Google session | Context-validated for corporate accounts |
| `SAPISID`, `APISID` | API session | Tied to the same context |

**What this means:** Cookies created on Machine A are **rejected** when used from Machine B, even if both are on the same corporate network. This is a deliberate security feature to prevent session hijacking.

### 2. Why Only Cloudtop Works

We tested **6 different deployment approaches** before arriving at the current solution. All failed due to the context-binding described above:

| Approach | Result | Failure Reason |
|----------|--------|----------------|
| **Cloud Run** | Failed | Cloud Run's public IP is outside Google's corporate network — cookies rejected |
| **Cloud Shell** | Failed | Cloud Shell's egress IP is not recognized as corporate context — cookies rejected |
| **Browser-like headers** | Failed | Cookie validation is not based on User-Agent or headers — it's IP/context-based |
| **noVNC + Playwright** | Failed | Hardware security key (YubiKey/Titan) cannot be forwarded through VNC |
| **OAuth tokens** | Failed | NotebookLM does not accept OAuth bearer tokens — only browser cookies |
| **Cookie transfer (Chromebook → Cloudtop)** | Failed | Cookies are bound to the Chromebook's context, rejected from Cloudtop |
| **Cloudtop (Chrome + CDP)** | Works | Cookies created on Cloudtop, used from Cloudtop = same context |

Full investigation details: [AUTH_INVESTIGATION_REPORT.md](AUTH_INVESTIGATION_REPORT.md)

### 3. Why Cookies Need Constant Refreshing

Google's corporate session cookies have **aggressive expiration policies**:

- Session cookies rotate every **20–60 minutes**
- The CSRF token (`SNlM0e`) embedded in the NotebookLM page changes with each session refresh
- `notebooklm-py` validates cookies by making an HTTP request to `notebooklm.google.com` — if the response is a redirect to `accounts.google.com`, the cookies are expired

**Without the CDP refresh mechanism**, a user would need to manually extract cookies from Chrome DevTools every 20–60 minutes. The CDP approach automates this by pulling fresh cookies from the running Chrome session (which auto-renews its own cookies internally).

### 4. Hardware Security Key Constraint

@google.com accounts require **hardware security key** (YubiKey/Titan) for 2FA via WebAuthn/FIDO2. This creates an additional constraint:

- The security key must be **physically accessible** to the machine performing sign-in
- On Cloudtop (accessed via Chrome Remote Desktop), the security key is on the **Chromebook**, not on the Cloudtop VM
- The `gcert` mechanism (gnubby agent) which normally forwards security key operations is **unreliable** (gnubby Error 512)
- Solution: sign in via Chrome on Cloudtop desktop (Chrome Remote Desktop forwards WebAuthn to the local security key), then extract cookies from that browser session

---

## Why This Cannot Be Deployed to Production

| Limitation | Impact |
|------------|--------|
| **Requires a running Chrome instance** | A Chrome browser must be open 24/7 on Cloudtop, signed into @google.com |
| **Single-user architecture** | Tied to one person's Google session — cannot serve multiple users |
| **Cookies expire every 20–60 min** | Requires constant CDP cookie extraction — fragile and resource-intensive |
| **Cloudtop-only** | Cannot run on Cloud Run, GKE, or any standard deployment platform |
| **No public API** | Built on reverse-engineered internal endpoints — can break without notice |
| **Security key required for initial sign-in** | Cannot be automated — requires human interaction via Chrome Remote Desktop |
| **Session hijacking risk** | Extracting and replaying cookies between processes (Chrome → Python) is inherently fragile |

### Summary

The current solution works as a **proof-of-concept demo** on Cloudtop, but it is fundamentally limited by:

1. **NotebookLM's lack of a public API** — forcing reliance on reverse-engineered cookie-based auth
2. **Google's corporate cookie security** (UberProxy/GSSO) — preventing deployment outside the cookie's originating context
3. **Cookie expiration policies** — requiring constant refresh from a live browser session

---

## Recommended Path to Production

### Option 1: Wait for NotebookLM API (Ideal)

If Google releases a public NotebookLM API with OAuth support, all authentication limitations are resolved. Standard OAuth tokens work across any deployment platform.

**Status:** No public API announced as of March 2026.

### Option 2: Replace NotebookLM with Gemini API (Available Now)

The Gemini API provides equivalent Q&A capabilities with **proper OAuth authentication**:

1. Upload the same source documents to Gemini's context window
2. Use the Gemini API (which supports OAuth/API keys) for Q&A
3. Deploy to Cloud Run or any standard platform

**Trade-offs:**
- Loses NotebookLM's specialized document understanding and citation features
- Requires managing document uploads and context windows
- Gains: proper auth, multi-user support, standard deployment, no cookie hacking

### Option 3: Use a Non-Corporate Google Account

Using a personal @gmail.com account (shared as a collaborator on the notebook) would bypass GSSO/UberProxy context binding. Consumer Google cookies have **longer expiration** and **less strict context validation**.

**Trade-offs:**
- Requires sharing notebooks with a non-corporate account
- May violate organizational data policies
- Still relies on reverse-engineered API (no stability guarantee)

### Option 4: Browser-in-the-Loop Architecture

Run a headless browser (Playwright/Puppeteer) as a persistent service that maintains a live Google session and proxies API calls through it. The browser handles cookie renewal automatically.

**Trade-offs:**
- More robust than CDP cookie extraction
- Still requires initial manual sign-in with security key
- Resource-intensive (running a full browser process)
- Still single-user, still on Cloudtop
