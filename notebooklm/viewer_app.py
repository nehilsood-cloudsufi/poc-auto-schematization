"""NotebookLM Viewer — Streamlit chat app for querying NotebookLM notebooks."""

import asyncio
import re

import nest_asyncio
import streamlit as st

nest_asyncio.apply()


def run_async(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "nlm_client": None,
    "notebook_id": None,
    "notebook_url": "",
    "connected": False,
    "connection_error": None,
    "sources": [],
    "chat_history": [],
}


def _init_state():
    for key, val in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NB_RE = re.compile(r"notebooklm\.google\.com/notebook/([a-zA-Z0-9_-]+)")


def _extract_notebook_id(url: str) -> str | None:
    m = _NB_RE.search(url)
    return m.group(1) if m else None


async def _create_client():
    """Create and initialize the NotebookLM client."""
    from notebooklm import NotebookLMClient

    client = await NotebookLMClient.from_storage()
    # Initialize the client (equivalent to async with __aenter__)
    await client.__aenter__()
    return client


async def _connect(notebook_id: str):
    """Create client, verify connectivity by listing sources."""
    client = await _create_client()

    # Try listing sources to verify connection
    sources = []
    try:
        raw = await client.sources.list(notebook_id)
        sources = [{"title": getattr(s, "title", str(s)), "id": getattr(s, "id", "")} for s in raw]
    except Exception:
        # View-only notebooks may not support source listing — that's OK
        pass

    return client, sources


async def _ask(client, notebook_id: str, prompt: str) -> str:
    """Send a chat message and return the response text."""
    resp = await client.chat.ask(notebook_id, prompt)
    # notebooklm-py returns a response object with .answer
    if isinstance(resp, str):
        return resp
    return getattr(resp, "answer", getattr(resp, "text", str(resp)))


async def _disconnect(client):
    """Cleanly close the client."""
    try:
        await client.__aexit__(None, None, None)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.set_page_config(page_title="NotebookLM Viewer", page_icon="📓", layout="wide")

with st.sidebar:
    st.title("📓 NotebookLM Viewer")
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
        disconnect_clicked = st.button(
            "Disconnect",
            use_container_width=True,
            disabled=not st.session_state["connected"],
        )

    # --- Connect ---
    if connect_clicked and url:
        nb_id = _extract_notebook_id(url)
        if not nb_id:
            st.session_state["connection_error"] = (
                "Invalid URL. Expected: https://notebooklm.google.com/notebook/<id>"
            )
            st.session_state["connected"] = False
        else:
            st.session_state["connection_error"] = None
            st.session_state["notebook_url"] = url
            st.session_state["notebook_id"] = nb_id

            with st.spinner("Connecting..."):
                try:
                    client, sources = run_async(_connect(nb_id))
                    st.session_state["nlm_client"] = client
                    st.session_state["sources"] = sources
                    st.session_state["connected"] = True
                    st.session_state["chat_history"] = []
                except Exception as exc:
                    import traceback
                    err = str(exc)
                    tb = traceback.format_exc()
                    st.session_state["connection_error"] = f"Connection failed: {err}\n\nTraceback:\n```\n{tb}\n```"
                    st.session_state["connected"] = False

    # --- Disconnect ---
    if disconnect_clicked and st.session_state["nlm_client"]:
        run_async(_disconnect(st.session_state["nlm_client"]))
        st.session_state["nlm_client"] = None
        st.session_state["connected"] = False
        st.session_state["notebook_id"] = None
        st.session_state["sources"] = []
        st.session_state["chat_history"] = []

    # --- Status ---
    st.markdown("---")
    if st.session_state["connected"]:
        st.success(f"Connected  \nNotebook: `{st.session_state['notebook_id']}`")
    elif st.session_state["connection_error"]:
        st.error(st.session_state["connection_error"])
    else:
        st.info("Paste a NotebookLM URL and click Connect.")

    # --- Sources ---
    if st.session_state["sources"]:
        with st.expander(f"Sources ({len(st.session_state['sources'])})", expanded=False):
            for src in st.session_state["sources"]:
                st.markdown(f"- {src['title']}")


# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------

if not st.session_state["connected"]:
    st.markdown(
        "### Welcome to NotebookLM Viewer\n\n"
        "Connect to a NotebookLM notebook using the sidebar, then chat with it here."
    )
else:
    # Render chat history
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask a question..."):
        # Show user message
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    answer = run_async(
                        _ask(
                            st.session_state["nlm_client"],
                            st.session_state["notebook_id"],
                            prompt,
                        )
                    )
                    st.markdown(answer)
                    st.session_state["chat_history"].append(
                        {"role": "assistant", "content": answer}
                    )
                except Exception as exc:
                    err_msg = f"Error: {exc}"
                    st.error(err_msg)
                    st.session_state["chat_history"].append(
                        {"role": "assistant", "content": err_msg}
                    )
