# Setup and Running Guide

How to configure, run, and deploy the React + FastAPI UI.

---

## Prerequisites

- **Python 3.12+** with `uv` package manager
- **Node.js 20+** with `npm`
- **GEMINI_API_KEY** in `.env` file (required for pipeline execution)

---

## First-Time Setup

### 1. Install Python dependencies

```bash
cd /path/to/poc-auto-schematization
uv sync --all-extras
source .venv/bin/activate
export PYTHONPATH="$(pwd):$(pwd)/src"
```

### 2. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Verify `.env` file exists

```bash
# .env (project root)
GEMINI_API_KEY=your-key-here

# Optional
GOOGLE_SHEET_ID=your-sheet-id     # For developer feedback → Google Sheets
GCS_BUCKET=your-bucket-name       # For Cloud Run GCS links
```

---

## Running in Development Mode

Development mode gives you **hot reload** on both frontend and backend — changes appear instantly without restarting.

### Terminal 1: FastAPI backend (port 8000)

```bash
cd /path/to/poc-auto-schematization
PYTHONPATH="$(pwd):$(pwd)/src" uvicorn src.api.main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

### Terminal 2: React dev server (port 5173)

```bash
cd /path/to/poc-auto-schematization/frontend
npm run dev
```

You should see:
```
VITE v6.x.x  ready in XXXms

➜  Local:   http://localhost:5173/
```

### Open the app

Go to **http://localhost:5173** in your browser.

The Vite dev server automatically proxies `/api/*` and `/ws/*` requests to the FastAPI backend on port 8000. This is configured in `frontend/vite.config.ts`.

---

## Running in Production Mode

Production mode serves everything from a single process — FastAPI serves the pre-built React static files.

### 1. Build the frontend

```bash
cd frontend
npm run build
cd ..
```

This creates `frontend/dist/` with optimized static assets.

### 2. Start the server

```bash
PYTHONPATH="$(pwd):$(pwd)/src" uvicorn src.api.main:app --port 8000
```

### 3. Open the app

Go to **http://localhost:8000**. Both the UI and API are served from the same port.

---

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Host to bind the API server |
| `API_PORT` | `8000` | Port for the API server |
| `UI_OUTPUT_DIR` | `ui_output` | Directory where run outputs are stored |
| `GEMINI_API_KEY` | (required) | Google Gemini API key for pipeline |
| `GOOGLE_SHEET_ID` | (optional) | Google Sheet ID for developer feedback |
| `GCS_BUCKET` | (optional) | GCS bucket name for Cloud Run output links |
| `K_SERVICE` | (auto) | Set automatically on Cloud Run |

### Pipeline Settings (configured in UI)

These are set via the Configure page in the wizard:

| Setting | Default | Description |
|---------|---------|-------------|
| Max Retries | 1 | Retry attempts after initial generation (0-10) |
| MCP Discovery | Off | Enable DC MCP server for StatVar discovery |
| Schema Examples | On | Inject schema vocabulary into PVMAP prompt |
| Model | gemini-3.1-pro-preview | Gemini model for generation |
| Human Feedback | (empty) | Pre-seed the pipeline with guidance text |

---

## Docker Deployment (Cloud Run)

### Build the Docker image

```bash
docker build -t pvmap-ui .
```

The `Dockerfile` uses a two-stage build:
1. **Stage 1**: Builds the React frontend (`npm run build`)
2. **Stage 2**: Copies Python code + built frontend into a slim Python image

### Run locally with Docker

```bash
docker run -p 8080:8080 \
  -e GEMINI_API_KEY=your-key \
  pvmap-ui
```

Open **http://localhost:8080**.

### Deploy to Cloud Run

```bash
gcloud run deploy pvmap-ui \
  --source . \
  --port 8080 \
  --set-env-vars GEMINI_API_KEY=your-key
```

---

## API Endpoints Reference

The backend exposes these REST endpoints (all under `/api/`):

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload CSV + optional metadata |
| `POST` | `/api/runs` | Start a pipeline run |
| `GET` | `/api/runs` | List all runs (active + historical) |
| `GET` | `/api/runs/{id}` | Get run status and result |
| `GET` | `/api/runs/{id}/files` | List output files |
| `GET` | `/api/runs/{id}/files/{name}` | Read a specific output file |
| `PUT` | `/api/runs/{id}/files/{name}` | Save an edited file |
| `POST` | `/api/runs/{id}/revalidate` | Re-run validation on edited PVMAP |
| `POST` | `/api/runs/{id}/feedback` | Submit feedback and trigger re-run |
| `POST` | `/api/runs/{id}/dev-feedback` | Submit developer feedback |
| `GET` | `/api/runs/{id}/download` | Download all outputs as ZIP |

### WebSocket

| Path | Description |
|------|-------------|
| `ws://host/ws/progress/{run_id}` | Real-time pipeline progress events |

### Interactive API docs

FastAPI auto-generates interactive docs:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Troubleshooting

### Frontend won't start

```
Error: Cannot find module '@tailwindcss/vite'
```

Run `cd frontend && npm install` to install dependencies.

### API returns 422 on upload

The upload endpoint expects `multipart/form-data` with a file field named `input_csv`. Make sure you're not sending JSON.

### WebSocket won't connect

In dev mode, WebSocket connections are proxied through Vite. Make sure both the FastAPI server (port 8000) and Vite dev server (port 5173) are running.

### CORS errors

In dev mode, CORS is configured to allow `http://localhost:5173` and `http://localhost:3000`. If you're running on a different port, update `src/api/main.py` in the `CORSMiddleware` config.

### Pipeline fails immediately

Check that `GEMINI_API_KEY` is set in your `.env` file and that the `.env` file is in the project root (not in `src/` or `frontend/`).

---

## Useful Commands

```bash
# Run all tests (Python)
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q

# Run only API tests
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/ -x -q

# Build frontend
cd frontend && npm run build

# Check frontend for type errors (without building)
cd frontend && npx tsc --noEmit
```
