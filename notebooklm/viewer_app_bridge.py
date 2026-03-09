"""NotebookLM Viewer — Streamlit chat app using browser bridge for auth."""

import json
import time

import requests
import streamlit as st

BRIDGE_URL = "http://localhost:8081"

_DEFAULTS = {
    "notebook_id": None,
    "notebook_url": "",
    "connected": False,
    "bridge_connected": False,
    "chat_history": [],
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.set_page_config(page_title="NotebookLM Viewer", page_icon="\U0001f4d3", layout="wide")


def _check_bridge():
    """Check if bridge server is running."""
    try:
        r = requests.get(BRIDGE_URL, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _ask_via_bridge(notebook_id: str, question: str, timeout: int = 60) -> str:
    """Send question through bridge, wait for browser JS to answer."""
    # Post question
    requests.post(
        f"{BRIDGE_URL}/question",
        json={"question": question, "notebook_id": notebook_id},
        timeout=5,
    )

    # Poll for answer
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(BRIDGE_URL, timeout=2)
        state = r.json()
        if state["status"] == "answered" and state["answer"]:
            # Reset for next question
            requests.post(f"{BRIDGE_URL}/reset", timeout=2)
            return state["answer"]
        time.sleep(0.5)

    requests.post(f"{BRIDGE_URL}/reset", timeout=2)
    return "Timeout: no response from browser bridge. Is the JS snippet running in the NotebookLM tab?"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

import re
_NB_RE = re.compile(r"notebooklm\.google\.com/notebook/([a-zA-Z0-9_-]+)")

with st.sidebar:
    st.title("\U0001f4d3 NotebookLM Viewer")
    st.markdown("---")

    # Bridge status
    bridge_ok = _check_bridge()
    if bridge_ok:
        st.success("Bridge relay: running")
    else:
        st.error("Bridge relay: not running")

    st.markdown("---")

    url = st.text_input(
        "NotebookLM URL",
        value=st.session_state["notebook_url"],
        placeholder="https://notebooklm.google.com/notebook/...",
    )

    col1, col2 = st.columns(2)
    with col1:
        connect_clicked = st.button("Connect", use_container_width=True)
    with col2:
        disconnect_clicked = st.button("Disconnect", use_container_width=True, disabled=not st.session_state["connected"])

    if connect_clicked and url:
        m = _NB_RE.search(url)
        if not m:
            st.error("Invalid URL")
        else:
            st.session_state["notebook_id"] = m.group(1)
            st.session_state["notebook_url"] = url
            st.session_state["connected"] = True
            st.session_state["chat_history"] = []

    if disconnect_clicked:
        for k, v in _DEFAULTS.items():
            st.session_state[k] = v
        requests.post(f"{BRIDGE_URL}/reset", timeout=2)

    if st.session_state["connected"]:
        st.success(f"Notebook: `{st.session_state['notebook_id']}`")

    # JS snippet instructions
    st.markdown("---")
    st.markdown("### Setup: Browser Bridge")
    st.markdown(
        "1. Open your NotebookLM notebook in another tab\n"
        "2. Press **Ctrl+Shift+I** → **Console** tab\n"
        "3. Paste the JS snippet below and press Enter"
    )

    # Build the JS snippet - user needs to replace BRIDGE_URL with their Web Preview URL
    with st.expander("JS Snippet (click to copy)", expanded=False):
        st.markdown(
            "**Replace `BRIDGE_URL`** with your Cloud Shell Web Preview URL for **port 8081**.\n\n"
            "To get it: click Web Preview → Change Port → 8081 → copy the URL."
        )
        st.code(
            """// NotebookLM Browser Bridge
// Replace this URL with your Cloud Shell Web Preview URL for port 8081
const BRIDGE = "https://8081-cs-XXXX-default.cloudshell.dev";

// Extract CSRF and session tokens from page
const html = document.documentElement.innerHTML;
const csrf = html.match(/"SNlM0e":"([^"]+)"/)?.[1];
const sid = html.match(/"FdrFJe":"([^"]+)"/)?.[1];

if (!csrf || !sid) {
    console.error("Could not extract tokens. Make sure you are on a NotebookLM notebook page.");
} else {
    console.log("Bridge active. CSRF:", csrf.slice(0,10) + "...");

    async function poll() {
        while (true) {
            try {
                const r = await fetch(BRIDGE);
                const state = await r.json();

                if (state.status === "pending" && state.question) {
                    console.log("Question:", state.question);
                    try {
                        const answer = await askNotebookLM(state.notebook_id, state.question);
                        await fetch(BRIDGE + "/answer", {
                            method: "POST",
                            headers: {"Content-Type": "application/json"},
                            body: JSON.stringify({answer})
                        });
                        console.log("Answered:", answer.slice(0, 80) + "...");
                    } catch (e) {
                        await fetch(BRIDGE + "/answer", {
                            method: "POST",
                            headers: {"Content-Type": "application/json"},
                            body: JSON.stringify({answer: "Error: " + e.message})
                        });
                    }
                }
            } catch (e) {
                // Bridge unavailable, retry
            }
            await new Promise(r => setTimeout(r, 1000));
        }
    }

    async function askNotebookLM(notebookId, question) {
        const params = JSON.stringify([
            [null, null, null, null, null, null, null, null, null, null, null, null,
             null, null, null, null, null, null, null, null, null, null, null, null,
             null, null, null, null, null, null, null, null, null, null, question],
            null, null, null, null, null, null, null, null, null, null, null, null,
            [notebookId]
        ]);

        const body = new URLSearchParams({
            "f.req": JSON.stringify([[["M35iqd", params, null, "generic"]]]),
            at: csrf
        });

        const url = "https://notebooklm.google.com/_/LabsTailwindUi/data/batchexecute?"
            + new URLSearchParams({
                "rpcids": "M35iqd",
                "f.sid": sid,
                "bl": "boq_labs-tailwind-frontend_20250305.06_p0",
                "hl": "en",
                "_reqid": String(Math.floor(Math.random() * 900000) + 100000),
                "rt": "c"
            });

        const resp = await fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            body: body,
            credentials: "include"
        });

        const text = await resp.text();
        // Parse batchexecute response - extract answer text
        const lines = text.split("\\n");
        for (const line of lines) {
            if (line.startsWith("[") && line.includes("M35iqd")) {
                try {
                    const parsed = JSON.parse(line);
                    const inner = JSON.parse(parsed[0][2]);
                    return inner[0] || inner[1] || "No answer found in response";
                } catch(e) {}
            }
        }
        return text.slice(0, 500);
    }

    poll();
}""",
            language="javascript",
        )


# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------

if not st.session_state["connected"]:
    st.markdown(
        "### Welcome to NotebookLM Viewer\n\n"
        "1. Paste a NotebookLM URL in the sidebar and click **Connect**\n"
        "2. Open the NotebookLM notebook in another tab\n"
        "3. Paste the JS bridge snippet in that tab's DevTools Console\n"
        "4. Start chatting here!"
    )
else:
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question..."):
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Waiting for browser bridge response..."):
                answer = _ask_via_bridge(st.session_state["notebook_id"], prompt)
                st.markdown(answer)
                st.session_state["chat_history"].append({"role": "assistant", "content": answer})
