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

## Setup

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

## Viewer App

A standalone Streamlit chat app for querying view-only NotebookLM notebooks. Deployed to Cloud Run — no ADK or Gemini dependency.

### Files

| File | Purpose |
|------|---------|
| `viewer_app.py` | Streamlit chat UI |
| `Dockerfile.viewer` | Container with Playwright/Chromium |
| `deploy_viewer.sh` | Cloud Run deploy script |
| `startup_viewer.sh` | Container entrypoint |
| `requirements_viewer.txt` | Deps (streamlit, notebooklm-py, nest-asyncio) |
| `.streamlit/config.toml` | Streamlit server config |

### Auth Setup

Auth uses `notebooklm-py` browser automation. The credentials (`storage_state.json`) must be generated on a machine logged into the google.com account that has NotebookLM access.

**Step 1 — Chromebook Cloud Shell (one-time):**
```bash
pip install "notebooklm-py[browser]" && playwright install chromium
notebooklm login
# Download: Cloud Shell menu → Download file → ~/.notebooklm/storage_state.json
```

**Step 2 — Store as GCP secret:**
```bash
gcloud secrets create NOTEBOOKLM_STORAGE_STATE \
  --data-file=~/Downloads/storage_state.json \
  --project=<PROJECT_ID>
```

**To refresh expired auth:** Repeat Step 1, then:
```bash
gcloud secrets versions add NOTEBOOKLM_STORAGE_STATE \
  --data-file=~/Downloads/storage_state.json
```

### Deploy

```bash
cd notebooklm
bash deploy_viewer.sh              # uses current gcloud project
bash deploy_viewer.sh PROJECT_ID   # explicit project
```

### Local Dev

```bash
cd notebooklm
pip install -r requirements_viewer.txt
playwright install chromium
streamlit run viewer_app.py
```

Note: Chat requires a valid `~/.notebooklm/storage_state.json` locally.
