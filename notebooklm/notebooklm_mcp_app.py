"""NotebookLM MCP Viewer — Streamlit chat app using the official Google
NotebookLM MCP server (corp-mcp-proxy).

Prerequisites:
    1. gLinux/Cloudtop with corp-mcp-proxy available
    2. Authenticated via GAIA/MOMA

Launch:
    source .venv/bin/activate
    PYTHONPATH="$(pwd):$(pwd)/src" streamlit run notebooklm/notebooklm_mcp_app.py
"""

import asyncio
import json
import logging
import sys

import nest_asyncio
import streamlit as st

nest_asyncio.apply()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("nlm_mcp")


def _run(coro):
    """Run async coroutine safely inside Streamlit."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "connected": False,
    "notebook_id": "",
    "notebook_url": "",
    "chat_history": [],
    "error": None,
}

for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.set_page_config(page_title="NotebookLM MCP Viewer", page_icon="📓", layout="wide")

with st.sidebar:
    st.title("📓 NotebookLM MCP")
    st.caption("Official Google MCP Server")
    st.markdown("---")

    # --- List notebooks ---
    if st.button("📋 List Notebooks", use_container_width=True):
        with st.spinner("Loading..."):
            try:
                from notebooklm.tools import list_notebooks
                result = _run(list_notebooks())
                if result["success"]:
                    st.json(result["data"])
                else:
                    st.error(result["error"])
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")
    st.subheader("Connect to Notebook")

    nb_id = st.text_input(
        "Notebook ID",
        value=st.session_state["notebook_id"],
        placeholder="paste notebook ID here",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔗 Connect", use_container_width=True):
            if nb_id:
                # Test connection by listing sources
                with st.spinner("Connecting..."):
                    try:
                        from notebooklm.tools import list_sources
                        result = _run(list_sources(nb_id))
                        st.session_state["notebook_id"] = nb_id
                        st.session_state["connected"] = True
                        st.session_state["chat_history"] = []
                        st.session_state["error"] = None
                        st.success("Connected!")
                    except Exception as e:
                        st.session_state["error"] = str(e)
                        st.error(f"Connection failed: {e}")
            else:
                st.warning("Enter a notebook ID.")

    with col2:
        if st.button("➕ Create New", use_container_width=True):
            name = st.session_state.get("new_nb_name", "My Notebook")
            with st.spinner("Creating..."):
                try:
                    from notebooklm.tools import create_notebook
                    result = _run(create_notebook(name))
                    if result["success"]:
                        data = result["data"]
                        new_id = data.get("notebook_id", data.get("id", ""))
                        st.session_state["notebook_id"] = new_id
                        st.session_state["connected"] = True
                        st.session_state["chat_history"] = []
                        st.success(f"Created notebook: {new_id}")
                    else:
                        st.error(result["error"])
                except Exception as e:
                    st.error(f"Error: {e}")

    new_nb_name = st.text_input("New notebook name", value="My Notebook", key="new_nb_name")

    # --- Add source ---
    st.markdown("---")
    st.subheader("Add Source")
    source_type = st.selectbox("Type", ["url", "text", "google_drive"])
    source_content = st.text_area("Content (URL, Drive link, or text)", height=80)

    if st.button("➕ Add Source", use_container_width=True):
        if st.session_state["connected"] and source_content:
            with st.spinner("Adding source..."):
                try:
                    from notebooklm.tools import create_source
                    result = _run(create_source(
                        st.session_state["notebook_id"],
                        source_type,
                        source_content,
                    ))
                    if result["success"]:
                        st.success("Source added!")
                    else:
                        st.error(result["error"])
                except Exception as e:
                    st.error(f"Error: {e}")
        elif not st.session_state["connected"]:
            st.warning("Connect to a notebook first.")

    # --- Status ---
    st.markdown("---")
    if st.session_state["connected"]:
        st.success(f"Active: `{st.session_state['notebook_id'][:20]}...`")
    elif st.session_state["error"]:
        st.error(st.session_state["error"])
    else:
        st.info("Connect to a notebook to start chatting.")

# ---------------------------------------------------------------------------
# Main chat area
# ---------------------------------------------------------------------------

if not st.session_state["connected"]:
    st.markdown(
        "### Welcome to NotebookLM MCP Viewer\n\n"
        "**Setup:**\n"
        "1. Click **List Notebooks** to see your existing notebooks\n"
        "2. Enter a notebook ID and click **Connect**, or **Create New**\n"
        "3. Optionally add sources (URLs, text, Drive links)\n"
        "4. Start chatting — answers are grounded in your notebook sources\n\n"
        "**Requires:** gLinux/Cloudtop with corp-mcp-proxy"
    )
else:
    # Render chat history
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask a question about your notebook sources..."):
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Querying NotebookLM..."):
                try:
                    from notebooklm.tools import generate_answer
                    result = _run(generate_answer(
                        st.session_state["notebook_id"],
                        prompt,
                    ))

                    if result["success"]:
                        data = result["data"]
                        display = data.get("answer", data.get("text", json.dumps(data, indent=2)))
                    else:
                        display = f"Error: {result['error']}"

                    st.markdown(display)
                    st.session_state["chat_history"].append(
                        {"role": "assistant", "content": display}
                    )
                except Exception as e:
                    err = f"Error: {e}"
                    log.error("Chat error: %s", e)
                    st.error(err)
                    st.session_state["chat_history"].append(
                        {"role": "assistant", "content": err}
                    )
