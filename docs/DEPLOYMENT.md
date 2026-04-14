# Cloud Run Deployment Guide

This document covers deploying the Auto Schematization Agent (FastAPI + React) to Google Cloud Run.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  Cloud Run Instance (gen2)                                       │
│                                                                  │
│  ┌─────────────┐    ┌──────────────────────────────────────────┐ │
│  │ DC MCP Server│    │ FastAPI / Uvicorn (PID 1)               │ │
│  │ port 3000    │◄───│ port 8080                               │ │
│  │ (background) │    │                                          │ │
│  └─────────────┘    │  /health  ── healthcheck                 │ │
│                      │  /api/*   ── REST endpoints              │ │
│                      │  /ws/*    ── WebSocket progress          │ │
│                      │  /*       ── React SPA (frontend/dist/) │ │
│                      │                                          │ │
│                      │  ┌────────────┐  ┌────────────┐         │ │
│                      │  │ Pipeline   │  │ Progress   │         │ │
│                      │  │ Thread     │  │ Plugin     │         │ │
│                      │  │ (daemon)   │  │ (queue)    │         │ │
│                      │  └────────────┘  └────────────┘         │ │
│                      └──────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ GCS FUSE Volume Mount                                        │ │
│  │ /app/ui_output ↔ gs://{PROJECT}-auto-schematization-agent-output │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   Secret Manager      Google Sheets API    Gemini API
   (API keys)          (feedback rows)      (LLM calls)
```

**Container startup sequence:**
1. `startup.sh` starts the DC MCP server on port 3000 in background
2. Waits up to 30s for MCP health check (`/health`)
3. `exec uvicorn` replaces shell as PID 1 (receives SIGTERM for graceful shutdown)

## Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud` CLI)
- A GCP project with billing enabled
- Docker (for local testing only)

## GCP Infrastructure Setup

### 1. Configure gcloud

```bash
export GCP_PROJECT="your-project-id"
gcloud auth login
gcloud config set project $GCP_PROJECT
gcloud config set run/region us-central1
```

### 2. Enable APIs

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com
```

### 3. Create Artifact Registry Repository

```bash
gcloud artifacts repositories create auto-schematization-agent \
  --repository-format=docker \
  --location=us-central1 \
  --description="Auto Schematization Agent container images"
```

### 4. Create Secrets

```bash
# Get service account for IAM bindings
PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Gemini API key (required)
echo -n "your-gemini-api-key" | gcloud secrets create GOOGLE_API_KEY --data-file=-
gcloud secrets add-iam-policy-binding GOOGLE_API_KEY \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"

# Data Commons API key (required)
echo -n "your-dc-api-key" | gcloud secrets create DC_API_KEY --data-file=-
gcloud secrets add-iam-policy-binding DC_API_KEY \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"

# Google Sheet ID for developer feedback (optional)
echo -n "your-sheet-id" | gcloud secrets create GOOGLE_SHEET_ID --data-file=-
gcloud secrets add-iam-policy-binding GOOGLE_SHEET_ID \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
```

### 5. Create GCS Bucket

```bash
BUCKET="${GCP_PROJECT}-auto-schematization-agent-output"

gcloud storage buckets create gs://${BUCKET} \
  --location=us-central1 \
  --uniform-bucket-level-access

gcloud storage buckets add-iam-policy-binding gs://${BUCKET} \
  --member="serviceAccount:${SA}" --role="roles/storage.objectAdmin"
```

### 6. Google Sheets Setup (optional)

If using the developer feedback Google Sheet:

1. Create a Google Sheet (or use an existing one)
2. Share it with the service account as **Editor**: `{PROJECT_NUMBER}-compute@developer.gserviceaccount.com`
3. Store the Sheet ID in Secret Manager (step 4 above)

The header row is auto-written on first feedback submission:
`timestamp | run_id | dataset_name | category | feedback_text | pipeline_status | quality_score | exit_reason | attempts | model | mcp_enabled | gcs_output_link`

## Deploy

### One-Command Deploy

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh $GCP_PROJECT us-central1
```

This runs Cloud Build to create the Docker image (multi-stage: Node.js frontend build + Python backend), then deploys to Cloud Run. First build takes ~5 minutes.

### What the Deploy Script Does

1. Builds Docker image via Cloud Build and pushes to Artifact Registry
2. Deploys to Cloud Run with:
   - 2 vCPU, 4 GB memory
   - 1-hour request timeout (pipeline runs can be long)
   - Session affinity (WebSocket connections)
   - GCS FUSE volume mount at `/app/ui_output`
   - Secrets injected as environment variables
   - Public access (no authentication) — see IAP section for auth

### Manual Deploy (step by step)

```bash
PROJECT_ID="your-project-id"
REGION="us-central1"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/auto-schematization-agent/app:latest"
BUCKET="${PROJECT_ID}-auto-schematization-agent-output"

# Build
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" --timeout=1200

# Deploy
gcloud run deploy auto-schematization-agent \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 2 \
  --memory 4Gi \
  --timeout 3600 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 3 \
  --session-affinity \
  --execution-environment gen2 \
  --set-env-vars "PYTHONPATH=/app:/app/src,UI_OUTPUT_DIR=/app/ui_output,GCS_BUCKET=${BUCKET}" \
  --set-secrets "GOOGLE_API_KEY=GOOGLE_API_KEY:latest,DC_API_KEY=DC_API_KEY:latest,GOOGLE_SHEET_ID=GOOGLE_SHEET_ID:latest" \
  --add-volume "name=output-vol,type=cloud-storage,bucket=${BUCKET}" \
  --add-volume-mount "volume=output-vol,mount-path=/app/ui_output"
```

## IAP Authentication

To restrict access via Google Identity-Aware Proxy:

```bash
chmod +x deploy/setup_iap.sh
./deploy/setup_iap.sh $GCP_PROJECT us-central1
```

This enables IAP on the Cloud Run service and grants access to `@google.com` and `@cloudsufi.com` domains. See `deploy/setup_iap.sh` for details.

## Local Docker Testing

```bash
# Build (multi-stage: Node.js + Python)
docker build -t auto-schematization-agent:local .

# Run (pass API keys from local .env)
docker run --rm -it \
  -p 8080:8080 \
  -e PORT=8080 \
  -e GOOGLE_API_KEY="$(grep GOOGLE_API_KEY .env | cut -d= -f2)" \
  -e DC_API_KEY="$(grep DC_API_KEY .env | cut -d= -f2)" \
  auto-schematization-agent:local

# Verify
curl -f http://localhost:8080/health
open http://localhost:8080
```

## Cloud Run Configuration

| Setting | Value | Rationale |
|---------|-------|-----------|
| CPU | 2 vCPU | MCP server + FastAPI + pipeline thread + validation subprocess |
| Memory | 4 GB | DataFrames + LLM responses + MCP + raw log files |
| Timeout | 3600s (1 hr) | Pipeline runs 5-15 min; WebSocket must stay alive |
| Concurrency | 80 | Multiple users can access the UI simultaneously |
| Min instances | 0 | Scale to zero when idle (cost savings) |
| Max instances | 3 | Cap cost while allowing parallel users |
| Session affinity | ON | Required for WebSocket connections |
| Execution env | gen2 | Required for GCS FUSE volume mounts |

## Environment Variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `PYTHONPATH` | Set in deploy | `/app:/app/src` — import path resolution |
| `UI_OUTPUT_DIR` | Set in deploy | `/app/ui_output` — GCS FUSE mount point |
| `GCS_BUCKET` | Set in deploy | Bucket name for constructing GCS Console links in UI |
| `CORS_ORIGINS` | Set in deploy | Comma-separated extra CORS origins (optional) |
| `GOOGLE_API_KEY` | Secret Manager | Gemini API key for LLM calls |
| `DC_API_KEY` | Secret Manager | Data Commons API key for MCP server |
| `GOOGLE_SHEET_ID` | Secret Manager | Google Sheet ID for developer feedback (optional) |
| `K_SERVICE` | Auto (Cloud Run) | Non-empty on Cloud Run; used for `CLOUD_RUN` detection |
| `PORT` | Auto (Cloud Run) | Defaults to 8080; uvicorn binds to this |

## Persistent Storage

Output files are persisted via GCS FUSE:

- **Mount path**: `/app/ui_output`
- **GCS bucket**: `gs://{PROJECT}-auto-schematization-agent-output`
- **Structure**: `{run_id}/output/{dataset_name}/` per pipeline run

GCS FUSE makes the bucket transparent to Python's `pathlib.Path` operations — no code changes needed for file I/O.

Browse output in GCS Console:
```
https://console.cloud.google.com/storage/browser/{PROJECT}-auto-schematization-agent-output
```

## Structured Logging

On Cloud Run (`K_SERVICE` set), loggers emit JSON for Cloud Logging:

```json
{
  "severity": "INFO",
  "message": "Launching pipeline for dataset=my_dataset",
  "logger": "src.api",
  "module": "runs",
  "user_email": "user@cloudsufi.com",
  "run_id": "abc123-def456",
  "dataset_name": "my_dataset"
}
```

### Querying Logs

```bash
# All user events
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="auto-schematization-agent" AND jsonPayload.user_event!=""' \
  --project=$GCP_PROJECT --limit=20 --format=json

# Errors only
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="auto-schematization-agent" AND severity="ERROR"' \
  --project=$GCP_PROJECT --limit=10

# Filter by run_id
gcloud logging read \
  'resource.type="cloud_run_revision" AND jsonPayload.run_id="<your-run-id>"' \
  --project=$GCP_PROJECT

# Filter by user
gcloud logging read \
  'resource.type="cloud_run_revision" AND jsonPayload.user_email="user@cloudsufi.com"' \
  --project=$GCP_PROJECT
```

## File Structure

```
├── Dockerfile                  # Multi-stage container (Node.js + Python)
├── .dockerignore               # Docker build context exclusions
├── .gcloudignore               # Cloud Build context exclusions
├── deploy/
│   ├── deploy.sh               # One-command deploy script
│   ├── setup_iap.sh            # IAP authentication setup
│   └── startup.sh              # Container entrypoint (MCP + uvicorn)
├── requirements.txt            # Frozen pip dependencies (uv pip freeze)
├── frontend/                   # React + TypeScript + Vite
│   ├── src/
│   └── dist/                   # Built by Dockerfile Stage 1
└── src/api/
    ├── main.py                 # FastAPI app + SPA static serving
    ├── config.py               # CLOUD_RUN, GCS_BUCKET, logging config
    ├── middleware/
    │   └── auth.py             # IAP JWT verification + user identity
    ├── routes/
    │   ├── upload.py           # CSV upload
    │   ├── runs.py             # Run CRUD + pipeline start
    │   ├── plan.py             # Mapping plan workflow
    │   ├── feedback.py         # Pipeline + developer feedback
    │   ├── files.py            # Output file serving + editing
    │   └── revalidate.py       # Revalidation endpoint
    ├── ws/
    │   └── progress.py         # WebSocket progress streaming
    └── services/
        ├── pipeline_runner.py  # Background thread launcher
        ├── file_manager.py     # Run discovery, file ops
        ├── run_state.py        # In-memory + disk run tracking
        ├── feedback_store.py   # Local JSON feedback persistence
        ├── mcp_lifecycle.py    # MCP server session management
        ├── rlhf_log.py         # Per-run RLHF interaction logging
        ├── activity_log.py     # Per-user activity event log
        └── google_sheets_service.py # Sheets API integration
```

## Troubleshooting

### Container fails to start

Check Cloud Run logs for startup errors:
```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND severity>=ERROR' \
  --project=$GCP_PROJECT --limit=20
```

Common causes:
- Missing secret (check Secret Manager bindings)
- MCP server binary not found (check `datacommons-mcp` in `requirements.txt`)
- Frontend build failed (check Node.js stage in Cloud Build logs)

### MCP server not ready

The startup script waits 30s for MCP health. If it times out, the pipeline still works — the MCP toggle in the UI can be turned off.

Check MCP status:
```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND jsonPayload.message:"MCP"' \
  --project=$GCP_PROJECT --limit=10
```

### Google Sheets 403 error

```
gspread.exceptions.APIError: [403]: The caller does not have permission
```

**Fix**: Share the Google Sheet with the Cloud Run service account as Editor:
```bash
PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT --format='value(projectNumber)')
echo "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
# Share the sheet with this email as Editor
```

### Output files not persisting

Verify the GCS FUSE mount:
```bash
gcloud storage ls gs://${GCP_PROJECT}-auto-schematization-agent-output/ --recursive
```

If empty after a completed run, check that:
- `execution-environment` is `gen2` (required for GCS FUSE)
- Service account has `roles/storage.objectAdmin` on the bucket

### `.gitignore` vs `.gcloudignore`

Cloud Build uses `.gitignore` when no `.gcloudignore` exists. The `.gcloudignore` file provides explicit control over what gets uploaded to Cloud Build. Key difference:

- `.gitignore` has `/schema/` (root-anchored) to exclude the input schema directory
- `.gcloudignore` mirrors this so `src/data_commons/schema/` (Python package) is included in the build

If you see `ModuleNotFoundError: No module named 'src.data_commons.schema'`, check that `.gcloudignore` doesn't exclude `src/data_commons/schema/`.

## Updating Dependencies

```bash
# Update pyproject.toml, then:
uv sync --all-extras
uv pip freeze > requirements.txt

# Verify key packages
grep -E "fastapi|uvicorn|google-adk|google-genai|datacommons-mcp|pandas|gspread" requirements.txt

# Redeploy
./deploy/deploy.sh $GCP_PROJECT us-central1
```

## Cost Estimate

With `min-instances=0` (scale to zero):
- **Idle**: ~$0/month (no instances running)
- **Active use**: ~$0.10/hour per instance (2 vCPU, 4 GB)
- **GCS storage**: ~$0.02/GB/month
- **Cloud Build**: ~$0.003/build-minute

With `min-instances=1` (always warm, no cold starts):
- **Base cost**: ~$96/month for the always-on instance
