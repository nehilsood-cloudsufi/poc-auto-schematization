# Project Structure: Frontend + Backend

This document explains the `frontend/` and `src/api/` directory structures, and maps each file to the Streamlit component it replaced.

## Overview

The old UI was a single-process Streamlit app (`src/ui/app.py`). The new UI is split into two layers:

- **`src/api/`** — FastAPI backend (REST + WebSocket)
- **`frontend/`** — React + TypeScript app (Vite, served separately in dev, bundled in production)

---

## Backend: `src/api/`

```
src/api/
├── main.py                  # FastAPI app entry point
├── config.py                # Settings (ports, paths, CORS origins)
├── routes/
│   ├── upload.py            # POST /api/upload — receive CSV, create run dir
│   ├── runs.py              # GET/POST /api/runs — list, start, get run status
│   ├── files.py             # GET/PUT /api/runs/{id}/files — read/edit output files
│   ├── feedback.py          # POST /api/runs/{id}/feedback — save human feedback
│   └── revalidate.py        # POST /api/runs/{id}/revalidate — trigger revalidation
├── ws/
│   └── progress.py          # WS /api/ws/{run_id} — stream ProgressEvents to browser
└── services/
    ├── run_state.py          # RunState dataclass + in-memory registry
    ├── pipeline_runner.py    # Launches pipeline in thread, pushes events to queue
    ├── file_manager.py       # Read/write output files with version tracking
    ├── feedback_store.py     # Persist feedback JSON per version
    ├── revalidation_service.py  # Re-run validation on edited PVMAP
    ├── mcp_lifecycle.py      # Start/stop MCP servers alongside pipeline
    └── google_sheets_service.py  # Optional: push results to Google Sheets
```

### What each file replaced

| New file | Replaced Streamlit file |
|---|---|
| `src/api/main.py` | `src/ui/app.py` (app entry point) |
| `src/api/routes/upload.py` | Upload widget in `app.py` |
| `src/api/routes/runs.py` | Pipeline launch logic in `app.py` |
| `src/api/routes/files.py` | File editor tabs in `app.py` |
| `src/api/routes/feedback.py` | Feedback form in `app.py` |
| `src/api/routes/revalidate.py` | Revalidation button in `app.py` |
| `src/api/ws/progress.py` | Progress bar polling loop in `app.py` |
| `src/api/services/pipeline_runner.py` | `src/ui/services/pipeline_runner.py` |
| `src/api/services/file_manager.py` | `src/ui/services/file_manager.py` |
| `src/api/services/feedback_store.py` | `src/ui/services/feedback_store.py` |
| `src/api/services/revalidation_service.py` | `src/ui/services/revalidation_service.py` |
| `src/api/services/run_state.py` | `st.session_state` in Streamlit |

The services in `src/api/services/` are framework-agnostic — they don't import FastAPI or Streamlit. This makes them testable without either framework.

---

## Frontend: `frontend/`

```
frontend/
├── index.html               # HTML shell (single-page app entry point)
├── vite.config.ts           # Vite config: dev proxy /api → localhost:8000
├── tsconfig.json            # TypeScript compiler config
├── package.json             # npm dependencies + scripts
├── src/
│   ├── main.tsx             # React entry: renders <App /> into #root
│   ├── App.tsx              # Router: maps URL paths to page components
│   ├── App.css              # Global styles
│   ├── index.css            # Tailwind base styles
│   ├── pages/               # One component per route
│   │   ├── UploadPage.tsx   # Step 1: upload CSV dataset
│   │   ├── ConfigurePage.tsx  # Step 2: set pipeline options (retries, model, etc.)
│   │   ├── ProgressPage.tsx   # Step 3: live progress via WebSocket
│   │   ├── ResultsPage.tsx    # Step 4: view/edit output files, submit feedback
│   │   └── HistoryPage.tsx    # Browse past runs
│   ├── components/          # Reusable UI building blocks
│   │   ├── FileUploader.tsx    # Drag-and-drop CSV upload
│   │   ├── ProgressTracker.tsx # Live log + status indicator
│   │   ├── CsvEditor.tsx       # Editable PVMAP table
│   │   ├── CodeViewer.tsx      # Syntax-highlighted file viewer
│   │   ├── DataPreview.tsx     # Read-only CSV preview
│   │   ├── OutputViewer.tsx    # Tabbed output file browser
│   │   ├── FeedbackForm.tsx    # Human feedback textarea + submit
│   │   ├── DownloadButton.tsx  # Download file button
│   │   ├── WizardStepper.tsx   # Step indicator (Upload → Configure → Run → Results)
│   │   ├── Sidebar.tsx         # Navigation sidebar
│   │   └── ui/                 # shadcn/ui primitives (Button, Card, Input, etc.)
│   ├── hooks/
│   │   └── useWebSocket.ts  # Custom hook: connect to WS, collect messages, expose status
│   ├── lib/
│   │   ├── api.ts           # Typed fetch wrappers for every API endpoint
│   │   └── utils.ts         # Utility functions (cn() for Tailwind class merging, etc.)
│   └── types/
│       └── index.ts         # TypeScript interfaces (Run, FileEntry, FeedbackPayload, etc.)
└── dist/                    # Production build output (gitignored, served by FastAPI)
```

### What each page replaced

| New page | Replaced Streamlit section |
|---|---|
| `UploadPage.tsx` | `st.file_uploader()` in `app.py` |
| `ConfigurePage.tsx` | `st.sidebar` config widgets in `app.py` |
| `ProgressPage.tsx` | Progress bar + log expander in `app.py` |
| `ResultsPage.tsx` | Output file tabs + feedback form in `app.py` |
| `HistoryPage.tsx` | (new — not in Streamlit) |

### Key files to understand first

1. **`src/types/index.ts`** — start here. All data shapes used across the app.
2. **`src/lib/api.ts`** — how the frontend talks to the backend.
3. **`src/hooks/useWebSocket.ts`** — how live progress works.
4. **`src/App.tsx`** — routing: which URL shows which page.

---

## Dev vs Production Mode

**Development** (two processes, hot reload on both):
```bash
# Terminal 1: FastAPI with auto-reload
PYTHONPATH="$(pwd):$(pwd)/src" uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Vite dev server (port 5173)
cd frontend && npm run dev
```
Vite proxies all `/api` requests to `localhost:8000` (configured in `vite.config.ts`).

**Production** (single process):
```bash
cd frontend && npm run build
PYTHONPATH="$(pwd):$(pwd)/src" uvicorn src.api.main:app --port 8000
```
FastAPI mounts `frontend/dist/` as static files at `/`. The built JS/CSS are served directly from Python.

---

## Adding a New Feature

Example: add a "cancel run" button.

1. **Backend route**: add `DELETE /api/runs/{run_id}` in `src/api/routes/runs.py`
2. **Service logic**: add `cancel_run(run_id)` in `src/api/services/pipeline_runner.py`
3. **API client**: add `cancelRun(runId)` function in `frontend/src/lib/api.ts`
4. **Type**: add `"cancelled"` to the `Status` union in `frontend/src/types/index.ts`
5. **UI**: add a Cancel button in `frontend/src/pages/ProgressPage.tsx`
6. **Test**: add a test in `tests/api/test_runs.py`
