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

After your manager says "done," run the permission check script in **Cloud Shell**:

```bash
cd ~/poc-auto-schematization
chmod +x deploy_google/permission_check.sh
./deploy_google/permission_check.sh
```

The script checks all 9 required IAM roles and prints a summary with PASS/FAIL for each. If any fail, it generates a ready-to-send message for your manager listing the missing roles.

To check a different project:

```bash
./deploy_google/permission_check.sh my-other-project
```

---

## 4. GCP Infrastructure Creation

Run the infrastructure setup script in **Cloud Shell**. You only need to do this once per project.

```bash
cd ~/poc-auto-schematization
chmod +x deploy_google/infra_setup.sh
./deploy_google/infra_setup.sh
```

The script creates all required resources (APIs, Artifact Registry, secrets, GCS bucket) and is idempotent — safe to re-run if anything fails halfway. It will interactively prompt you for API keys:

- **Gemini API key** — get from https://aistudio.google.com/apikey
- **Data Commons API key** — get from https://apikeys.datacommons.org
- **Google Sheet ID** — optional, press Enter to skip

To use a different project/region:

```bash
./deploy_google/infra_setup.sh my-other-project europe-west4
```

**To update a secret later:**

```bash
echo -n "new-value" | gcloud secrets versions add GOOGLE_API_KEY --data-file=-
```

### (Optional) Google Sheets Setup

If using the developer feedback feature:

1. Create a Google Sheet (or use an existing one)
2. The script prints the service account email — share the sheet with it as **Editor**
3. The Sheet ID is stored in Secret Manager by the script

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
