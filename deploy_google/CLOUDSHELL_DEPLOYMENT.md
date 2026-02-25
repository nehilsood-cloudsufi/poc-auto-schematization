# Cloud Shell Deployment Guide

> **Audience:** xw@ (external workforce) deploying Agent B to `datcom-infosys-dev` / `europe-west1` from a Chromebook using Cloud Shell.
>
> **Branch:** `release/nehil/agentB_google_deploy`
>
> **What is Cloud Shell?** A free, browser-based terminal at console.cloud.google.com with `gcloud`, `git`, and `docker` pre-installed. Zero setup required.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Get GCP Access (Ask Your Manager)](#2-get-gcp-access-ask-your-manager)
3. [Permission Self-Check](#3-permission-self-check)
4. [GCP Infrastructure Creation](#4-gcp-infrastructure-creation)
5. [Deploy to Cloud Run](#5-deploy-to-cloud-run)
6. [Post-Deploy Verification](#6-post-deploy-verification)
7. [Daily Workflow Quick Reference](#7-daily-workflow-quick-reference)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Quick Start

### Open Cloud Shell

1. Open **https://console.cloud.google.com** in Chrome on your Chromebook
2. Set the project to **`datcom-infosys-dev`** using the project dropdown (top-left)
3. Click the **Cloud Shell** icon (terminal icon, top-right bar)
4. A terminal opens at the bottom of the page

> **Tip:** Click the "Open in new window" icon (top-right of the terminal pane) for a full-screen terminal.

### First-Time Setup (run once)

```bash
# Set project and region
gcloud config set project datcom-infosys-dev
gcloud config set run/region europe-west1

# Clone the repo (persists in your 5GB Cloud Shell home directory)
git clone https://github.com/nehilsood-cloudsufi/poc-auto-schematization.git
cd poc-auto-schematization
git checkout release/nehil/agentB_google_deploy
```

### Deploy (after infrastructure is set up — see Sections 2-4)

```bash
cd ~/poc-auto-schematization
git pull origin release/nehil/agentB_google_deploy

chmod +x deploy_google/deploy_cloudtop.sh
./deploy_google/deploy_cloudtop.sh
```

That's it. Cloud Build handles the Docker image build remotely on Google's servers. Your Chromebook just submits the commands.

### Cloud Shell Key Facts

| Feature | Detail |
|---------|--------|
| **Pre-installed tools** | `gcloud`, `git`, `docker`, `python3`, `vim`, `nano` |
| **Authentication** | Automatic — uses your Google login |
| **Persistent storage** | 5 GB home directory (survives restarts) |
| **Session timeout** | ~20 min idle (reconnect anytime, files persist) |
| **Weekly limit** | 50 hours/week (more than enough for deploys) |
| **Cost** | Free |
| **Local Streamlit?** | No — test on the deployed Cloud Run URL instead |

---

## 2. Get GCP Access (Ask Your Manager)

Before anything else, you need IAM roles on the GCP project. Copy-paste this message to your manager (or TL):

> **Subject: IAM roles needed on datcom-infosys-dev for Agent B deployment**
>
> Hi [Manager],
>
> I need access to the GCP project **`datcom-infosys-dev`** to deploy the Agent B (Auto-Schematization) Streamlit app to Cloud Run.
>
> **Project requirements:**
> - Billing enabled
> - Region: `europe-west1`
>
> **IAM roles I need on the project** (my account: `nehil@google.com` or your xw@ identity):
>
> | # | Role | Why |
> |---|------|-----|
> | 1 | `roles/editor` OR the individual roles below | Broad access (simplest) |
> | 2 | `roles/serviceusage.serviceUsageAdmin` | Enable APIs (Cloud Run, Build, etc.) |
> | 3 | `roles/run.admin` | Create/update Cloud Run services |
> | 4 | `roles/cloudbuild.builds.editor` | Submit Cloud Build jobs |
> | 5 | `roles/artifactregistry.admin` | Create repos + push Docker images |
> | 6 | `roles/secretmanager.admin` | Create/manage secrets (API keys) |
> | 7 | `roles/storage.admin` | Create GCS buckets for output |
> | 8 | `roles/iam.serviceAccountUser` | Bind service accounts to Cloud Run |
> | 9 | `roles/logging.viewer` | Read Cloud Logging for debugging |
>
> If `roles/editor` is too broad, the individual roles (2-9) are the minimum set.
>
> The project ID is **`datcom-infosys-dev`** and I'll deploy to **`europe-west1`**.
>
> Thanks!

**Wait for your manager's reply before proceeding.**

---

## 3. Permission Self-Check

After your manager says "done," run this in **Cloud Shell** to verify every required permission:

```bash
# ============================================================
# PERMISSION SELF-CHECK SCRIPT
# ============================================================

export PROJECT_ID="datcom-infosys-dev"
gcloud config set project "$PROJECT_ID"

echo "=== Permission Self-Check ==="
echo ""

# 1. Can I view the project?
echo "1. Project access (basic):"
gcloud projects describe $PROJECT_ID --format="value(projectId)" 2>&1 | head -3
echo "   PASS: shows project ID | FAIL: PERMISSION_DENIED"
echo ""

# 2. Can I enable APIs? (roles/serviceusage.serviceUsageAdmin)
echo "2. Enable APIs:"
gcloud services list --enabled --limit=1 2>&1 | head -3
echo "   PASS: shows a service | FAIL: PERMISSION_DENIED"
echo ""

# 3. Can I create Cloud Run services? (roles/run.admin)
echo "3. Cloud Run access:"
gcloud run services list --region=europe-west1 2>&1 | head -3
echo "   PASS: empty list or services | FAIL: PERMISSION_DENIED"
echo ""

# 4. Can I submit Cloud Builds? (roles/cloudbuild.builds.editor)
echo "4. Cloud Build access:"
gcloud builds list --limit=1 2>&1 | head -3
echo "   PASS: empty list or builds | FAIL: PERMISSION_DENIED"
echo ""

# 5. Can I manage Artifact Registry? (roles/artifactregistry.admin)
echo "5. Artifact Registry access:"
gcloud artifacts repositories list --location=europe-west1 2>&1 | head -3
echo "   PASS: empty list or repos | FAIL: PERMISSION_DENIED"
echo ""

# 6. Can I manage secrets? (roles/secretmanager.admin)
echo "6. Secret Manager access:"
gcloud secrets list 2>&1 | head -3
echo "   PASS: empty list or secrets | FAIL: PERMISSION_DENIED"
echo ""

# 7. Can I manage storage? (roles/storage.admin)
echo "7. GCS access:"
gcloud storage buckets list --limit=1 2>&1 | head -3
echo "   PASS: empty or buckets | FAIL: PERMISSION_DENIED"
echo ""

# 8. Can I use service accounts? (roles/iam.serviceAccountUser)
echo "8. Service Account access:"
gcloud iam service-accounts list 2>&1 | head -3
echo "   PASS: shows SA list | FAIL: PERMISSION_DENIED"
echo ""

# 9. Can I view logs? (roles/logging.viewer)
echo "9. Logging access:"
gcloud logging read "" --limit=1 --freshness=1d 2>&1 | head -3
echo "   PASS: empty or log entry | FAIL: PERMISSION_DENIED"
echo ""

echo "=== Self-Check Complete ==="
echo "If any check shows PERMISSION_DENIED, ask your manager to grant the corresponding role (see table in Section 2)."
```

**If any check fails**, reply to your manager with:

> Check #N failed with PERMISSION_DENIED. Could you grant me `roles/xxx` on project `datcom-infosys-dev`?

---

## 4. GCP Infrastructure Creation

Run all of these in **Cloud Shell**. You only need to do this once per project.

### 4.1 Set Variables

```bash
export PROJECT_ID="datcom-infosys-dev"
export REGION="europe-west1"
export BUCKET="${PROJECT_ID}-agent-b-output"

# Get the default compute service account
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
export SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Project: $PROJECT_ID"
echo "Service Account: $SA"
echo "Bucket: $BUCKET"
```

### 4.2 Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com
```

This takes ~30 seconds.

### 4.3 Create Artifact Registry Repository

```bash
gcloud artifacts repositories create agent-b \
  --repository-format=docker \
  --location=$REGION \
  --description="Agent B container images"
```

### 4.4 Create Secrets in Secret Manager

```bash
# Gemini API key (required)
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create GOOGLE_API_KEY --data-file=-
gcloud secrets add-iam-policy-binding GOOGLE_API_KEY \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"

# Data Commons API key (required)
echo -n "YOUR_DC_API_KEY" | gcloud secrets create DC_API_KEY --data-file=-
gcloud secrets add-iam-policy-binding DC_API_KEY \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"

# Google Sheet ID (optional — skip if not using feedback sheets)
echo -n "YOUR_SHEET_ID" | gcloud secrets create GOOGLE_SHEET_ID --data-file=-
gcloud secrets add-iam-policy-binding GOOGLE_SHEET_ID \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
```

**To update a secret later:**

```bash
echo -n "new-value" | gcloud secrets versions add GOOGLE_API_KEY --data-file=-
```

### 4.5 Create GCS Output Bucket

```bash
gcloud storage buckets create gs://${BUCKET} \
  --location=$REGION \
  --uniform-bucket-level-access

gcloud storage buckets add-iam-policy-binding gs://${BUCKET} \
  --member="serviceAccount:${SA}" --role="roles/storage.objectAdmin"
```

### 4.6 (Optional) Google Sheets Setup

If using the developer feedback feature:

1. Create a Google Sheet (or use an existing one)
2. Share it with the service account as **Editor**: copy the `$SA` email and add it as a sheet collaborator
3. Store the Sheet ID in Secret Manager (done in 4.4 above)

---

## 5. Deploy to Cloud Run

From **Cloud Shell**:

```bash
cd ~/poc-auto-schematization
git pull origin release/nehil/agentB_google_deploy

chmod +x deploy_google/deploy_cloudtop.sh
./deploy_google/deploy_cloudtop.sh
```

Defaults: project=`datcom-infosys-dev`, region=`europe-west1`. Override with positional args:

```bash
./deploy_google/deploy_cloudtop.sh my-other-project europe-west4
```

> **Note:** The existing `deploy/deploy.sh` is for CloudSufi (`us-central1`). Use `deploy_google/deploy_cloudtop.sh` for Google-side deployment.

**First build takes ~5-8 minutes.** Subsequent deploys: ~2-3 min (layer caching).

### What the Deploy Script Does

1. **`gcloud builds submit`** — Builds Docker image via Cloud Build and pushes to Artifact Registry (`europe-west1-docker.pkg.dev`)
2. **`gcloud run deploy`** — Creates/updates the Cloud Run service with:
   - 2 vCPU, 4 GB memory
   - 1-hour request timeout
   - Session affinity (required for Streamlit WebSocket)
   - GCS FUSE volume mount at `/app/ui_output`
   - Secrets injected as env vars from Secret Manager
   - Public access (no authentication)

### Get the URL

```bash
gcloud run services describe agent-b --region=europe-west1 --format='value(status.url)'
```

---

## 6. Post-Deploy Verification

```bash
export REGION="europe-west1"
export PROJECT_ID="datcom-infosys-dev"
export BUCKET="${PROJECT_ID}-agent-b-output"

# 1. Get the service URL
URL=$(gcloud run services describe agent-b --region=$REGION --format='value(status.url)')
echo "Service URL: $URL"

# 2. Health check
curl -sf "${URL}/_stcore/health"
# Expected: "ok"

# 3. Open in browser
echo "Open this in your Chromebook browser: $URL"

# 4. Check Cloud Run logs for startup
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="agent-b"' \
  --project=$PROJECT_ID --limit=20 --format="table(timestamp,jsonPayload.message)"

# 5. Verify GCS bucket is accessible
gcloud storage ls gs://${BUCKET}/
```

### Smoke Test

1. Open the Cloud Run URL in Chrome on your Chromebook
2. Upload a small CSV file
3. Click "Run Pipeline"
4. Wait for completion (~2-5 min)
5. Check output: `gcloud storage ls gs://${BUCKET}/ --recursive`

---

## 7. Daily Workflow Quick Reference

Open **Cloud Shell** (https://console.cloud.google.com → terminal icon), then:

```bash
# === Setup (every session) ===
cd ~/poc-auto-schematization
export PROJECT_ID="datcom-infosys-dev"
export REGION="europe-west1"

# === Pull latest code + deploy ===
git pull origin release/nehil/agentB_google_deploy
./deploy_google/deploy_cloudtop.sh

# === Check status ===
URL=$(gcloud run services describe agent-b --region=$REGION --format='value(status.url)')
curl -sf "${URL}/_stcore/health"

# === View logs ===
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="agent-b"' \
  --project=$PROJECT_ID --limit=20 --format="table(timestamp,jsonPayload.message)"

# === View output files ===
gcloud storage ls gs://${PROJECT_ID}-agent-b-output/ --recursive

# === Update a secret ===
echo -n "new-api-key" | gcloud secrets versions add GOOGLE_API_KEY --data-file=-
./deploy_google/deploy_cloudtop.sh   # Redeploy to pick up new secret
```

---

## 8. Troubleshooting

### Cloud Shell session disconnected

Cloud Shell times out after ~20 min idle. Just reopen it — your home directory (including the cloned repo) persists. Reconnect and `cd ~/poc-auto-schematization`.

If a deploy was interrupted mid-build, check if it's still running:

```bash
gcloud builds list --limit=3
# If status is WORKING, wait for it. If FAILURE, re-run the deploy.
```

### "PERMISSION_DENIED" during deploy

Go back to [Section 3](#3-permission-self-check) and re-run the self-check.

### Cloud Build fails or times out

```bash
gcloud builds list --limit=3
gcloud builds log $(gcloud builds list --limit=1 --format='value(id)')
```

Common causes:
- **Large context:** Check `.gcloudignore` is present and correct.
- **Timeout:** First build can take up to 20 min. The script sets `--timeout=1200`.

### Container crashes on startup

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND severity>=ERROR' \
  --project=datcom-infosys-dev --limit=20
```

Common causes:
- **Missing secret:** `gcloud secrets list`
- **Secret binding missing:** SA needs `secretAccessor` on each secret (see 4.4)
- **MCP binary missing:** Check `datacommons-mcp` in `requirements.txt`

### "ModuleNotFoundError" in Cloud Run

```bash
cat .gcloudignore
# Ensure it does NOT exclude src/ directories
```

### Google Sheets 403 error

The Cloud Run service account needs Editor access on the Google Sheet:

```bash
PROJECT_NUMBER=$(gcloud projects describe datcom-infosys-dev --format='value(projectNumber)')
echo "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
# Share the sheet with this email as Editor
```

### Output files not persisting (GCS empty after run)

```bash
# Check execution environment is gen2
gcloud run services describe agent-b --region=europe-west1 \
  --format='value(spec.template.metadata.annotations["run.googleapis.com/execution-environment"])'
# Must show: gen2
```

### Streamlit WebSocket disconnects

```bash
gcloud run services describe agent-b --region=europe-west1 \
  --format='value(spec.template.metadata.annotations["run.googleapis.com/sessionAffinity"])'
# Must show: true
```

---

## Appendix: Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│  Cloud Run Instance (gen2)                               │
│                                                          │
│  ┌─────────────┐    ┌──────────────────────────────────┐ │
│  │ DC MCP Server│    │ Streamlit (PID 1)               │ │
│  │ port 3000    │◄───│ port 8080                       │ │
│  │ (background) │    │                                  │ │
│  └─────────────┘    │  ┌────────────┐  ┌────────────┐ │ │
│                      │  │ Pipeline   │  │ Progress   │ │ │
│                      │  │ Thread     │  │ Plugin     │ │ │
│                      │  │ (daemon)   │  │ (queue)    │ │ │
│                      │  └────────────┘  └────────────┘ │ │
│                      └──────────────────────────────────┘ │
│                                                          │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ GCS FUSE Volume Mount                                │ │
│  │ /app/ui_output ↔ gs://datcom-infosys-dev-agent-b-output │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   Secret Manager      Google Sheets API    Gemini API
   (API keys)          (feedback rows)      (LLM calls)
```
