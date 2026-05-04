# UI Framework Migration: Streamlit to React + FastAPI

**Date:** 2026-04-07
**Branch:** `feature/nehil/ui-framework-migration`
**Status:** Design approved, pending implementation plan

---

## 1. Motivation

Replace the Streamlit-based UI (`src/ui/`) with a React + FastAPI stack for:

- **Production quality** — clean, minimal aesthetic with wizard flow; not a prototype look
- **Reactivity** — granular component updates instead of Streamlit's full-page rerender model
- **Rich interactivity** — drag-and-drop column mapping, inline mapping plan approval, editable spreadsheets
- **Deployment** — single Docker image for Cloud Run (FastAPI serves React static assets)
- **Maintainability** — team is Python-backend focused; FastAPI is the bulk of the work, React side is mostly wiring up shadcn/ui components

## 2. Target Users

- **Primary:** Development team (power users who understand the pipeline)
- **Secondary:** Occasional non-technical reviewers who upload data and inspect results

## 3. Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend framework | React 18 + TypeScript | Largest ecosystem, best AI tooling support, rich component libraries |
| Build tool | Vite | Fast dev server with HMR, instant builds, simple config |
| UI components | shadcn/ui (Tailwind CSS) | Copy-paste components, clean minimal aesthetic, fully customizable |
| Data tables | TanStack Table | Virtualized, editable cells, sorting, filtering — powers the PVMAP editor |
| Drag-and-drop | @dnd-kit/core | Column mapping feature (future phase) |
| Routing | React Router v6 | URL-based wizard steps, deep-linking to runs |
| API framework | FastAPI | Python-native, async, WebSocket support, auto-generated OpenAPI docs |
| Real-time | WebSocket (FastAPI) | Streaming pipeline progress events — replaces queue polling |
| State (server) | In-memory dict + disk | `RunState` keyed by run_id; persistent data on filesystem (output dirs, manifests) |

## 4. Architecture

```
┌─────────────────────────────────────────────────┐
│  FRONTEND (React + Vite + shadcn/ui)            │
│  Single Page App — wizard flow                  │
│  Communicates via REST + WebSocket              │
│  Served as static files by FastAPI in prod      │
├─────────────────────────────────────────────────┤
│  API LAYER (FastAPI)                            │
│  REST endpoints: /api/upload, /api/runs, etc.   │
│  WebSocket: /ws/progress/{run_id}               │
│  Replaces Streamlit session_state               │
├─────────────────────────────────────────────────┤
│  SERVICE LAYER (refactored from src/ui/)        │
│  Framework-agnostic Python services             │
│  pipeline_runner, file_manager, feedback_store   │
│  progress_plugin (queue → WebSocket bridge)     │
├─────────────────────────────────────────────────┤
│  PIPELINE (unchanged)                           │
│  src/run_pipeline.py, src/agents/*, src/pipeline│
└─────────────────────────────────────────────────┘
```

**Critical constraint:** The pipeline layer (`run_pipeline.py`, agents, etc.) stays completely untouched. Only `src/ui/` gets replaced. The service layer gets refactored to remove Streamlit imports and exposed via FastAPI routes.

## 5. Directory Structure

```
src/
├── api/                          # NEW — FastAPI backend
│   ├── __init__.py
│   ├── main.py                   # FastAPI app, CORS, static file mount
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── runs.py               # POST /api/runs, GET /api/runs, GET /api/runs/{id}
│   │   ├── upload.py             # POST /api/upload
│   │   ├── feedback.py           # POST /api/runs/{id}/feedback, /api/runs/{id}/dev-feedback
│   │   ├── files.py              # GET/PUT /api/runs/{id}/files/{name}
│   │   └── revalidate.py         # POST /api/runs/{id}/revalidate
│   ├── ws/
│   │   ├── __init__.py
│   │   └── progress.py           # WebSocket /ws/progress/{run_id}
│   ├── services/                 # Refactored from src/ui/services/
│   │   ├── __init__.py
│   │   ├── pipeline_runner.py    # launch_pipeline() — framework-agnostic
│   │   ├── file_manager.py       # No Streamlit imports
│   │   ├── feedback_store.py     # Unchanged (already clean)
│   │   ├── revalidation_service.py  # Unchanged
│   │   ├── google_sheets_service.py # Unchanged
│   │   ├── mcp_lifecycle.py      # Remove st.session_state, use RunState
│   │   └── run_state.py          # NEW — in-memory run tracking
│   └── adapters/
│       ├── __init__.py
│       └── progress_plugin.py    # ProgressTrackingPlugin (queue → WebSocket bridge)
│
frontend/                         # NEW — React app (project root, not inside src/)
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── components.json               # shadcn/ui config
├── src/
│   ├── App.tsx                   # Root component with React Router
│   ├── main.tsx                  # Entry point
│   ├── index.css                 # Tailwind imports + global styles
│   ├── pages/
│   │   ├── UploadPage.tsx        # Step 1: file upload + data preview
│   │   ├── ConfigurePage.tsx     # Step 2: pipeline settings
│   │   ├── ProgressPage.tsx      # Step 3: real-time progress via WebSocket
│   │   ├── ResultsPage.tsx       # Step 4: tabbed output viewer + actions
│   │   └── HistoryPage.tsx       # Browse past runs
│   ├── components/
│   │   ├── ui/                   # shadcn/ui components (auto-generated)
│   │   ├── FileUploader.tsx      # Drag-and-drop CSV upload
│   │   ├── DataPreview.tsx       # First-10-rows table
│   │   ├── ProgressTracker.tsx   # Phase checklist + progress bar
│   │   ├── OutputViewer.tsx      # Tabbed file viewer
│   │   ├── CsvEditor.tsx         # Editable spreadsheet (TanStack Table)
│   │   ├── CodeViewer.tsx        # Syntax-highlighted text (MCF, TMCF)
│   │   ├── FeedbackForm.tsx      # Feedback + re-run trigger
│   │   ├── DownloadButton.tsx    # ZIP download
│   │   ├── Sidebar.tsx           # Persistent nav + history + config summary
│   │   └── WizardStepper.tsx     # Step indicator (1→2→3→4)
│   ├── hooks/
│   │   ├── useWebSocket.ts       # WebSocket connection with auto-reconnect
│   │   ├── useRun.ts             # Run state management (start, poll, results)
│   │   └── useApi.ts             # Typed fetch wrapper
│   ├── lib/
│   │   ├── api.ts                # API client (base URL, error handling)
│   │   └── utils.ts              # Shared utilities (cn(), formatTime(), etc.)
│   └── types/
│       └── index.ts              # Shared TypeScript types (Run, PipelineConfig, ProgressEvent, etc.)
```

## 6. API Specification

### REST Endpoints

| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| `POST` | `/api/upload` | `multipart/form-data` (input_csv, metadata_csv?) | `{ run_id, dataset_name, input_path }` | Creates run dir, saves files |
| `POST` | `/api/runs` | `{ run_id, dataset_name, config: PipelineConfig }` | `{ run_id, status: "running" }` | Starts pipeline thread |
| `GET` | `/api/runs` | — | `[{ run_id, dataset_name, timestamp, status, result }]` | Sorted by timestamp desc |
| `GET` | `/api/runs/{id}` | — | `{ run_id, status, dataset_name, result, error }` | Current state of run |
| `GET` | `/api/runs/{id}/files` | — | `{ files: ["generated_pvmap.csv", ...] }` | List available output files |
| `GET` | `/api/runs/{id}/files/{name}` | — | File content (CSV as JSON array, text as string) | Content-type aware |
| `PUT` | `/api/runs/{id}/files/{name}` | `{ content: [...rows] }` or `{ text: "..." }` | `{ saved: true }` | Save edited file |
| `POST` | `/api/runs/{id}/revalidate` | — | `{ success, data_rows, error }` | Runs stat_var_processor |
| `POST` | `/api/runs/{id}/feedback` | `{ text, category, severity }` | `{ run_id (new), status: "running" }` | Snapshots, starts re-run |
| `POST` | `/api/runs/{id}/dev-feedback` | `{ text, category }` | `{ saved: true }` | Bug report to Sheets + local |
| `GET` | `/api/runs/{id}/download` | — | `application/zip` | ZIP of all output files |

### WebSocket

**Endpoint:** `ws://localhost:8000/ws/progress/{run_id}`

**Server → Client messages:**
```json
{ "type": "progress", "agent": "Validator", "message": "Validator completed", "attempt": 1, "timestamp": 1712500000 }
{ "type": "complete", "result": { "validation_passed": true, "exit_reason": "quality_pass", ... } }
{ "type": "error", "message": "Pipeline failed: ...", "traceback": "..." }
{ "type": "plan_ready", "plan": { ... } }  // Future: mapping plan approval
```

## 7. Frontend Wizard Flow

```
[1. Upload] → [2. Configure] → [3. Running] → [4. Results]
                                     ↑              |
                                     └──────────────┘ (feedback re-run)
```

### Page 1: Upload (`/`)
- Drag-and-drop zone for CSV (with fallback file picker)
- Optional metadata CSV upload
- Auto-detect dataset name from filename (editable)
- Data preview: first 10 rows in a read-only table
- Validation: reject empty CSVs, show row/column count

### Page 2: Configure (`/configure`)
- Pipeline settings: max retries (slider 0-10), model selector
- Toggles: MCP enabled, Schema Examples
- Optional: pre-seeded human feedback text area
- "Generate PVMAP" → POST /api/upload + POST /api/runs → navigate to Running

### Page 3: Running (`/runs/{id}`)
- Connects to WebSocket on mount
- Phase checklist: ordered list of pipeline phases with status icons
  - Green check: completed
  - Blue spinner: in progress
  - Gray circle: pending
- Attempt indicator: "Attempt 2 of 3"
- Elapsed time counter (client-side, updates every second)
- Progress bar (completed phases / total phases)
- Auto-navigates to Results on terminal event
- Future: pauses for mapping plan approval when `plan_ready` event arrives

### Page 4: Results (`/runs/{id}/results`)
- **Result banner**: pass/fail, attempt count, exit reason
- **Tab bar**: PVMAP | Metadata Config | Processed Data | MCF | TMCF | StatVars | Notes | Metrics
- **PVMAP tab**: Editable spreadsheet (TanStack Table) with add/delete rows, Save button
- **Other CSV tabs**: Read-only table
- **Text tabs**: Syntax-highlighted code viewer with copy button
- **Notes**: Rendered markdown
- **Actions**: Save & Revalidate button, Download ZIP button
- **Feedback section** (embedded): text area, category dropdown, severity slider, "Re-run" button

### Sidebar (all pages)
- App title: "Agent B: Auto Schematization" + status pill
- Active run info (run_id, GCS link)
- "New Run" button (when complete/error)
- History: last 10 runs, click to load results
- Config summary (collapsed expander)

## 8. Run State Management

```python
@dataclass
class RunState:
    run_id: str
    status: str          # idle | running | complete | error
    dataset_name: str
    config: dict         # PipelineConfig as dict
    run_dir: Path
    result: dict = field(default_factory=dict)
    error: Optional[str] = None
    progress_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=100))
    thread: Optional[threading.Thread] = None
    created_at: float = field(default_factory=time.time)

# In-memory store — single process, no external dependencies
_runs: dict[str, RunState] = {}
```

- Active runs tracked in memory for WebSocket broadcasting
- Completed run data lives on disk (output dirs, manifests, feedback JSONs)
- `GET /api/runs` merges in-memory active runs with disk-based historical runs
- No database required — intentionally simple for single-process deployment

## 9. Service Layer Refactoring

Changes needed to make services framework-agnostic:

| File | Current Streamlit Coupling | Change |
|------|---------------------------|--------|
| `pipeline_runner.py` | None (already clean) | Move to `src/api/services/`, keep as-is |
| `file_manager.py` | `save_uploaded_file()` takes Streamlit `UploadedFile` | Accept `bytes` + filename instead |
| `feedback_store.py` | None | Move as-is |
| `revalidation_service.py` | None | Move as-is |
| `google_sheets_service.py` | None | Move as-is |
| `mcp_lifecycle.py` | Uses `st.session_state` for server handle | Store in `RunState` or module-level dict |
| `progress_plugin.py` | None (already uses queue.Queue) | Add WebSocket broadcast loop |
| `config.py` | `PHASE_LABELS` only used for display | Move to API config, share with frontend via endpoint or constants |

## 10. Deployment

### Development mode (two processes)
```bash
# Terminal 1: FastAPI backend
cd src && uvicorn api.main:app --reload --port 8000

# Terminal 2: React dev server (hot reload)
cd frontend && npm run dev   # port 5173, proxies /api → localhost:8000
```

### Production mode (single container)
```dockerfile
# Stage 1: Build React
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/ .
RUN npm ci && npm run build

# Stage 2: Python app
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --all-extras
COPY src/ src/
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
ENV PYTHONPATH=/app:/app/src
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

FastAPI serves the built React assets:
```python
# src/api/main.py
app.mount("/", StaticFiles(directory="frontend/dist", html=True))
```

### Local quick-start
```bash
# Build frontend once
cd frontend && npm install && npm run build && cd ..

# Run everything
PYTHONPATH="$(pwd):$(pwd)/src" uvicorn src.api.main:app --port 8000
# Open http://localhost:8000
```

## 11. Testing Strategy

### Backend (Python)
- **Unit tests** for each route (FastAPI TestClient)
- **Service tests** reuse existing test patterns
- **WebSocket tests** using `httpx` async client
- Run with: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`

### Frontend (TypeScript)
- **Component tests** with Vitest + React Testing Library
- **E2E tests** with Playwright (future, not in initial build)
- Run with: `cd frontend && npm test`

## 12. Features: Must-Have (Phase 1)

All 12 existing Streamlit features, migrated:

1. File upload (CSV + metadata)
2. Real-time progress tracker (WebSocket)
3. Tabbed output viewer (PVMAP, Metadata, MCF, TMCF, StatVars, Notes, Metrics)
4. Inline CSV editor (PVMAP + metadata)
5. Save & Revalidate
6. Feedback form + re-run with human feedback injection
7. Output versioning (v1/, v2/ snapshots)
8. Download as ZIP
9. Run history
10. Developer feedback (Google Sheets + local JSON)
11. MCP toggle + configuration
12. GCS integration (Cloud Run links)

## 13. Features: Enhanced (Phase 1.5)

- **Inline mapping plan approval** — WebSocket `plan_ready` event pauses the Running page, shows approve/edit/reject UI
- **Drag-and-drop column mapper** — visual column-to-property mapping (new page between Configure and Running)

## 14. Migration Strategy

1. Build FastAPI backend (refactor services, create routes, test with curl)
2. Build React frontend (page by page, connect to real API)
3. Remove Streamlit (`src/ui/`, `streamlit` dependency)
4. Update CLAUDE.md, docs, and learning documentation

Old `src/ui/` stays untouched until new system is fully working. Deleted in one commit at the end.

## 15. Learning Documentation

Maintain `docs/frontend-guide/` with:
- `01-react-basics.md` — components, props, state, hooks (mapped to Python concepts)
- `02-typescript-for-python-devs.md` — types, interfaces, generics
- `03-project-structure.md` — what each file does and why
- `04-shadcn-ui-guide.md` — how to add/customize components
- `05-fastapi-react-integration.md` — how the two talk to each other
- `06-development-workflow.md` — dev mode, building, testing, deploying

Updated incrementally as features are built.
