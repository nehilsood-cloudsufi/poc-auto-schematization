#!/bin/bash
set -e

echo "=== NotebookLM Viewer — Cloud Shell Setup ==="
echo ""

# Step 1: Create directory
mkdir -p ~/notebooklm-viewer/.streamlit
cd ~/notebooklm-viewer

# Step 2: Write requirements
cat > requirements.txt << 'EOF'
streamlit>=1.44.0
notebooklm-py>=0.3.0
nest-asyncio>=1.6.0
EOF

# Step 3: Write Streamlit config
cat > .streamlit/config.toml << 'EOF'
[server]
headless = true
enableCORS = false
enableXsrfProtection = false
maxUploadSize = 10

[browser]
gatherUsageStats = false
EOF

# Step 4: Write the app
cat > viewer_app.py << 'PYEOF'
import asyncio, re, os, traceback
import nest_asyncio, streamlit as st
nest_asyncio.apply()

def run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

_DEFAULTS = {"nlm_client": None, "notebook_id": None, "notebook_url": "", "connected": False, "connection_error": None, "sources": [], "chat_history": []}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

_NB_RE = re.compile(r'notebooklm\.google\.com/notebook/([a-zA-Z0-9_-]+)')

async def _connect(notebook_id):
    from notebooklm import NotebookLMClient
    client = await NotebookLMClient.from_storage()
    sources = []
    try:
        raw = await client.sources.list(notebook_id)
        sources = [{"title": getattr(s, "title", str(s)), "id": getattr(s, "id", "")} for s in raw]
    except Exception:
        pass
    return client, sources

async def _ask(client, notebook_id, prompt):
    resp = await client.chat.ask(notebook_id, prompt)
    return resp if isinstance(resp, str) else getattr(resp, "text", str(resp))

async def _disconnect(client):
    try: await client.close()
    except: pass

st.set_page_config(page_title="NotebookLM Viewer", page_icon="\U0001f4d3", layout="wide")
with st.sidebar:
    st.title("\U0001f4d3 NotebookLM Viewer")
    st.markdown("---")
    url = st.text_input("NotebookLM URL", value=st.session_state["notebook_url"], placeholder="https://notebooklm.google.com/notebook/...")
    col1, col2 = st.columns(2)
    with col1: connect_clicked = st.button("Connect", use_container_width=True)
    with col2: disconnect_clicked = st.button("Disconnect", use_container_width=True, disabled=not st.session_state["connected"])
    if connect_clicked and url:
        nb_id = _NB_RE.search(url)
        if not nb_id:
            st.session_state["connection_error"] = "Invalid URL. Expected: https://notebooklm.google.com/notebook/<id>"
            st.session_state["connected"] = False
        else:
            nb_id = nb_id.group(1)
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
                    st.session_state["connection_error"] = f"Connection failed: {exc}\n\n```\n{traceback.format_exc()}\n```"
                    st.session_state["connected"] = False
    if disconnect_clicked and st.session_state["nlm_client"]:
        run_async(_disconnect(st.session_state["nlm_client"]))
        for k, v in _DEFAULTS.items(): st.session_state[k] = v
    st.markdown("---")
    if st.session_state["connected"]:
        st.success(f"Connected\nNotebook: `{st.session_state['notebook_id']}`")
    elif st.session_state["connection_error"]:
        st.error(st.session_state["connection_error"])
    else:
        st.info("Paste a NotebookLM URL and click Connect.")
    if st.session_state["sources"]:
        with st.expander(f"Sources ({len(st.session_state['sources'])})", expanded=False):
            for src in st.session_state["sources"]:
                st.markdown(f"- {src['title']}")

if not st.session_state["connected"]:
    st.markdown("### Welcome to NotebookLM Viewer\n\nConnect to a NotebookLM notebook using the sidebar, then chat with it here.")
else:
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt := st.chat_input("Ask a question..."):
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    answer = run_async(_ask(st.session_state["nlm_client"], st.session_state["notebook_id"], prompt))
                    st.markdown(answer)
                    st.session_state["chat_history"].append({"role": "assistant", "content": answer})
                except Exception as exc:
                    err_msg = f"Error: {exc}"
                    st.error(err_msg)
                    st.session_state["chat_history"].append({"role": "assistant", "content": err_msg})
PYEOF

# Step 5: Check storage_state.json exists
if [ ! -f "$HOME/.notebooklm/storage_state.json" ]; then
    echo ""
    echo "ERROR: ~/.notebooklm/storage_state.json not found."
    echo "Run the cookie extraction step first."
    exit 1
fi
echo "Found storage_state.json with $(python3 -c "import json; print(len(json.load(open('$HOME/.notebooklm/storage_state.json'))['cookies']))" 2>/dev/null || echo '?') cookies"

# Step 6: Install deps
echo ""
echo "Installing dependencies..."
pip install -q -r requirements.txt 2>&1 | tail -3

# Step 7: Launch
echo ""
echo "=== Starting Streamlit on port 8080 ==="
echo ">>> Click the Web Preview button (eye icon, top-right) and select 'Preview on port 8080'"
echo ""
streamlit run viewer_app.py \
    --server.port=8080 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false \
    --server.fileWatcherType=none
