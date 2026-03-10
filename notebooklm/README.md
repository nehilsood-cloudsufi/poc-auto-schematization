# NotebookLM + Google ADK Integration

Programmatic access to Google NotebookLM using [notebooklm-py](https://github.com/teng-lin/notebooklm-py) as the transport layer, wrapped with [Google ADK](https://github.com/google/adk-python) agents and tool functions.

## Architecture

```
notebooklm-py (async client)     <-- transport layer (browser automation)
    |
tools.py                         <-- ADK tool functions wrapping notebooklm-py
    |
agents.py                        <-- ADK agents (LlmAgent + BaseAgent)
    |
viewer_app.py                    <-- Streamlit chat app (standalone)
    |
demos/                           <-- ADK demo scripts (not needed for viewer)
    01_*.py ... 06_*.py
    main.py
```

### Tool Layer (`tools.py`)

Async functions that wrap `notebooklm-py` methods. Each returns `{"success": bool, "data": ..., "error": str}` (matching the `src/tools/` convention in this project). A module-level client singleton manages the browser session.

**Tools:** `create_notebook`, `delete_notebook`, `list_notebooks`, `add_url_source`, `add_youtube_source`, `add_text_source`, `add_file_source`, `ask_question`, `generate_audio`, `download_audio`, `generate_video`, `download_video`, `generate_report`, `download_report`, `generate_quiz`, `download_quiz`, `start_research`

### Agent Layer (`agents.py`)

| Agent | Type | Purpose |
|-------|------|---------|
| `ResearchAgent` | LlmAgent | Interactive research — the LLM decides what tools to call |
| `DataAnalysisAgent` | LlmAgent | Analyze CSV datasets from our `input/` directory |
| `PodcastPipelineAgent` | BaseAgent | Deterministic pipeline: research -> podcast -> download |
| `BulkImportAgent` | BaseAgent | Concurrent multi-source import with status reporting |

---

## Viewer App — Cloudtop Deployment (Recommended)

The viewer app runs on **Cloudtop** (gLinux VM). This is the only working auth approach for @google.com accounts — see [AUTH_INVESTIGATION_REPORT.md](AUTH_INVESTIGATION_REPORT.md) for why.

### Prerequisites

- A **Cloudtop** VM (request one at go/cloudtop if you don't have one)
- **Chrome Remote Desktop** access to Cloudtop (go/crd)
- Your **hardware security key** (YubiKey/Titan) for Google sign-in

### Step 1: Connect to Cloudtop Desktop

1. On your Chromebook, open Chrome and go to: **go/crd** (Chrome Remote Desktop)
2. Find your Cloudtop machine and click **Connect**
3. Open a **Terminal** on the Cloudtop desktop:
   - Right-click desktop → "Open Terminal", or press `Ctrl+Alt+T`

### Step 2: First-Time Setup (one command)

In the Cloudtop terminal, run:

```bash
curl -sL https://raw.githubusercontent.com/nehilsood-cloudsufi/poc-auto-schematization/feature/nehil/notebooklm-agentb/notebooklm/setup_cloudtop.sh | bash
```

**What happens automatically:**
- Clones the repo to `~/work/poc-auto-schematization/`
- Installs Python packages (streamlit, notebooklm-py, playwright)
- Downloads Chromium browser for Playwright
- Opens a Chromium browser window for Google sign-in

**What you do manually:**
- A browser window opens on the Cloudtop desktop
- Sign in with your **@google.com** account
- When prompted, **tap your security key** (YubiKey/Titan)
- After sign-in succeeds, the browser closes automatically
- The script continues and launches the Streamlit app

### Step 3: Open the App

**Option A — Cloudtop browser (easiest):**
Open Firefox/Chrome on the Cloudtop desktop → go to `http://localhost:8501`

**Option B — Chromebook browser (better experience):**
1. On your Chromebook, open a new terminal
2. Run: `ssh -L 8501:localhost:8501 <your-cloudtop-hostname>`
   (e.g., `ssh -L 8501:localhost:8501 nehilsood.c.googlers.com`)
3. Open Chrome on Chromebook → go to `http://localhost:8501`

### Step 4: Use the App

1. In the sidebar, paste your NotebookLM notebook URL
2. Click **Connect**
3. Type questions in the chat input
4. Get answers from NotebookLM!

### Step 5: Daily Use (subsequent days)

No need to re-install. Just run:

```bash
curl -sL https://raw.githubusercontent.com/nehilsood-cloudsufi/poc-auto-schematization/feature/nehil/notebooklm-agentb/notebooklm/run_cloudtop.sh | bash
```

**If your session expired** (auth errors after ~2 weeks):

```bash
curl -sL https://raw.githubusercontent.com/nehilsood-cloudsufi/poc-auto-schematization/feature/nehil/notebooklm-agentb/notebooklm/run_cloudtop.sh | bash -s -- --reauth
```

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "DISPLAY not set" error | You're SSHed without a desktop. Use Chrome Remote Desktop (go/crd) instead. |
| Browser doesn't open during setup | Make sure you're on the Cloudtop desktop, not SSH. |
| "Connection failed" in the app | Cookies expired. Run `run_cloudtop.sh --reauth` to re-authenticate. |
| Can't access from Chromebook | Check the SSH tunnel is running. The `ssh -L ...` terminal must stay open. |
| Port 8501 already in use | Kill the old process: `pkill -f streamlit` then re-run. |

---

## Setup (Local / ADK Demos)

### 1. Install dependencies

```bash
pip install "notebooklm-py[browser]" google-adk
playwright install chromium
```

### 2. Authenticate with Google

```bash
notebooklm login
```

This opens a browser for Google sign-in. Credentials are saved to `~/.notebooklm/storage_state.json`.

### 3. Set Gemini API key (for ADK agents)

```bash
export GEMINI_API_KEY="your-api-key"
```

## Running Demos

### Individual scripts

```bash
cd notebooklm/demos

# Quickstart: create notebook, add source, ask question, generate audio
python 01_quickstart.py

# Multi-turn chat with diverse sources
python 02_sources_and_chat.py

# Generate artifacts (audio, report, quiz)
python 03_generate_artifacts.py

# Research-to-podcast pipeline (pass topic as argument)
python 04_research_to_podcast.py "quantum computing advances 2025"

# Bulk import multiple sources concurrently
python 05_bulk_import.py

# Analyze a project CSV dataset
python 06_use_with_our_data.py --dataset bis_bis_central_bank_policy_rate
python 06_use_with_our_data.py --file ../../input/my_dataset/test_data/input_data.csv
```

### Coordinated runner

```bash
cd notebooklm/demos

# Interactive menu
python main.py

# Run specific demo
python main.py --demo quickstart
python main.py --demo podcast --topic "AI in healthcare"
python main.py --demo data --dataset bis_bis_central_bank_policy_rate

# List available demos
python main.py --list
```

## Scripts Overview

| Script | Agent Used | What it does |
|--------|-----------|-------------|
| `demos/01_quickstart.py` | ResearchAgent | Single-turn: create notebook, add URL, ask question, generate audio |
| `demos/02_sources_and_chat.py` | ResearchAgent | Multi-turn: add diverse sources, chat with follow-ups |
| `demos/03_generate_artifacts.py` | ResearchAgent | Generate audio podcast, briefing report, and quiz |
| `demos/04_research_to_podcast.py` | PodcastPipelineAgent | Deterministic: research topic -> generate podcast -> download |
| `demos/05_bulk_import.py` | BulkImportAgent | Concurrent import of URLs, YouTube, text sources |
| `demos/06_use_with_our_data.py` | DataAnalysisAgent | Upload project CSV, ask schema questions, generate briefing |

## ADK Patterns Used

This integration follows the same ADK patterns as the main project (`src/agents/`):

- **LlmAgent factory functions** — `create_research_agent()`, `create_data_analysis_agent()` return configured agents (like `src/agents/schema_selection_agent.py`)
- **BaseAgent with `_run_async_impl`** — `PodcastPipelineAgent`, `BulkImportAgent` for deterministic pipelines (like `src/agents/validation_agent.py`)
- **Tool return format** — `{"success": bool, "data": ..., "error": str}` (like `src/tools/schema_tools.py`)
- **Runner + InMemorySessionService** — standard ADK execution pattern
- **Session state** — agents read/write state for inter-step communication
- **No `{...}` in instructions** — uses `[...]` for non-state placeholders to avoid ADK template resolution bugs

## Notes

- All scripts use `async/await` — Python 3.10+ required
- Auth token is reused from `~/.notebooklm/storage_state.json`
- Audio/video generation can take 1-5 minutes depending on content length
- The `shutdown_client()` call at the end of each script cleanly closes the browser session

---

## Deprecated Approaches

The following approaches were investigated and **do not work** for @google.com accounts due to context-bound session cookies (GSSO/UberProxy). See [AUTH_INVESTIGATION_REPORT.md](AUTH_INVESTIGATION_REPORT.md) for full details.

| Approach | Why it failed |
|----------|--------------|
| Cloud Run deployment | Cookies are context-bound — Cloud Run's IP is rejected |
| Cloud Shell | Same issue — Cloud Shell egress IP not on corporate network |
| Browser-like headers | Cookie validation is not header-based |
| noVNC + Playwright login | Hardware security key can't be forwarded through VNC |
| OAuth tokens | NotebookLM doesn't accept OAuth — only browser cookies |
| Browser bridge (JS relay) | Unnecessary complexity — Cloudtop solves the auth problem directly |
