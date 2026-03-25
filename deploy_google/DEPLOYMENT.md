# Auto-Schematization — Deployment Guide

> **One guide for all deployment paths.** Whether you're on Cloudtop, Cloud Shell, or a Chromebook, this covers everything.
>
> **Project:** `datcom-infosys-dev` | **Region:** `europe-west1` | **Branch:** `release/nehil/agentB_google_deploy`

---

## Table of Contents

1. [Overview & Architecture](#1-overview--architecture)
2. [Prerequisites](#2-prerequisites)
3. [First-Time Deployment](#3-first-time-deployment)
4. [Redeployment (After Code Changes)](#4-redeployment-after-code-changes)
5. [Accessing the App](#5-accessing-the-app)
6. [Managing User Access](#6-managing-user-access)
7. [Pain Points & Solutions](#7-pain-points--solutions)
8. [Local Development (Cloudtop)](#8-local-development-cloudtop)
9. [Cloud Shell Quick Start](#9-cloud-shell-quick-start)
10. [Troubleshooting](#10-troubleshooting)
11. [Script Reference](#11-script-reference)
12. [Configuration Reference](#12-configuration-reference)

---

## 1. Overview & Architecture

Auto-Schematization is a Streamlit app deployed to **Cloud Run (gen2)** behind **Identity-Aware Proxy (IAP)**. Users open the Cloud Run URL in their browser, Google handles OAuth login, and IAP injects the authentication token — no proxy or Cloud Shell session needed.

```
Browser (user)
    │
    ▼
Identity-Aware Proxy (IAP)
    │  ← Google OAuth login + token injection
    ▼
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

**How IAP works:**
1. User opens `*.run.app` URL in browser
2. Google prompts for OAuth login (if not already signed in)
3. IAP validates the user is authorized (google.com domain, datcom-cloudsufi, or datcom-core group)
4. IAP injects a Bearer token into the request
5. Cloud Run receives authenticated request and serves Streamlit

---

## 2. Prerequisites

### Required IAM Roles

Copy-paste this to your manager:

> **Subject: IAM roles needed on datcom-infosys-dev for Auto-Schematization deployment**
>
> I need access to GCP project **`datcom-infosys-dev`** to deploy the Auto-Schematization Streamlit app.
>
> **IAM roles needed** (for my account):
>
> | # | Role | Why |
> |---|------|-----|
> | 1 | `roles/serviceusage.serviceUsageAdmin` | Enable APIs |
> | 2 | `roles/run.admin` | Create/update Cloud Run services |
> | 3 | `roles/cloudbuild.builds.editor` | Submit Cloud Build jobs |
> | 4 | `roles/artifactregistry.admin` | Create repos + push Docker images |
> | 5 | `roles/secretmanager.admin` | Create/manage secrets (API keys) |
> | 6 | `roles/storage.admin` | Create GCS buckets |
> | 7 | `roles/iam.serviceAccountUser` | Bind service accounts to Cloud Run |
> | 8 | `roles/logging.viewer` | Read Cloud Logging |
>
> Alternatively, `roles/editor` covers all of the above.

Run `./deploy_google/permission_check.sh` to verify which roles you have.

### Required API Keys

| Key | Where to Get It |
|-----|-----------------|
| Gemini API key | https://aistudio.google.com/apikey |
| Data Commons API key | https://apikeys.datacommons.org |
| Google Sheet ID | Optional — for developer feedback feature |

### Required Tools

- `gcloud` CLI with `beta` component: `gcloud components install beta`
- Git

---

## 3. First-Time Deployment

**Single command does everything:**

```bash
git clone https://github.com/nehilsood-cloudsufi/poc-auto-schematization.git
cd poc-auto-schematization
git checkout release/nehil/agentB_google_deploy

./deploy_google/setup_and_deploy.sh
```

The script runs 8 steps:

| Step | What It Does |
|------|-------------|
| 1. Permission check | Validates all 9 IAM roles |
| 2. Enable APIs | Cloud Run, Cloud Build, Secret Manager, Storage, Artifact Registry, IAP |
| 3. Create infrastructure | Artifact Registry repo, secrets (prompts for API keys), GCS bucket |
| 4. Fix build permissions | Grants storage + AR write to Compute SA and Cloud Build SA |
| 5. Build & push image | `gcloud builds submit` (~5-8 min first time, ~2-3 min after) |
| 6. Deploy to Cloud Run | Sets CPU, memory, secrets, GCS FUSE, session affinity, IAP |
| 7. Grant access | `roles/run.invoker` to google.com domain + project groups |
| 8. Configure IAP | IAP service agent, `roles/iap.httpsResourceAccessor` grants |

Override defaults with positional args:

```bash
./deploy_google/setup_and_deploy.sh my-project europe-west4
```

---

## 4. Redeployment (After Code Changes)

Use the quick deploy script — skips infrastructure setup (~2-3 min):

```bash
git pull origin release/nehil/agentB_google_deploy
./deploy_google/deploy_cloudtop.sh
```

This does 3 steps:
1. **Pre-flight checks** — verifies Artifact Registry, secrets, and GCS bucket exist
2. **Build & push** — `gcloud builds submit` (layer caching makes rebuilds fast)
3. **Deploy** — `gcloud beta run deploy` with all config flags + IAP

### When to Use Which Script

| Scenario | Script |
|----------|--------|
| First-time deployment | `setup_and_deploy.sh` |
| Code change, infra already exists | `deploy_cloudtop.sh` |
| IAP got disabled (403 errors) | `setup_iap.sh` |
| Need to recreate infra (secrets, bucket) | `setup_and_deploy.sh` |
| Rotating API keys | Update secret, then `deploy_cloudtop.sh` |

---

## 5. Accessing the App

**Just open the Cloud Run URL in your browser.** That's it.

```bash
# Get the URL
gcloud run services describe auto-schematization --region=europe-west1 --format='value(status.url)'
```

1. Open the URL in Chrome
2. Google prompts you to sign in (if not already)
3. Streamlit app loads

No proxy. No Cloud Shell session. No port forwarding.

### Health Check (for debugging)

```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  $(gcloud run services describe auto-schematization --region=europe-west1 --format='value(status.url)')/_stcore/health
# Expected: "ok"
```

---

## 6. Managing User Access

### Currently Granted Access

- `domain:google.com` — all @google.com accounts
- `group:datcom-cloudsufi@google.com`
- `group:datcom-core@google.com`

### Add Individual Users

```bash
# Cloud Run invoker (required)
gcloud run services add-iam-policy-binding auto-schematization \
  --region=europe-west1 \
  --member="user:someone@google.com" \
  --role="roles/run.invoker"

# IAP access (required for browser access)
gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run --service=auto-schematization --region=europe-west1 \
  --member="user:someone@google.com" --role="roles/iap.httpsResourceAccessor" \
  --condition=None
```

### Add Google Groups

```bash
gcloud run services add-iam-policy-binding auto-schematization \
  --region=europe-west1 \
  --member="group:my-team@google.com" \
  --role="roles/run.invoker"

gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run --service=auto-schematization --region=europe-west1 \
  --member="group:my-team@google.com" --role="roles/iap.httpsResourceAccessor" \
  --condition=None
```

### Remove Access

```bash
gcloud run services remove-iam-policy-binding auto-schematization \
  --region=europe-west1 \
  --member="user:someone@google.com" \
  --role="roles/run.invoker"

gcloud beta iap web remove-iam-policy-binding \
  --resource-type=cloud-run --service=auto-schematization --region=europe-west1 \
  --member="user:someone@google.com" --role="roles/iap.httpsResourceAccessor"
```

---

## 7. Pain Points & Solutions

Every issue we hit during deployment and the fix:

| Problem | Root Cause | Solution |
|---------|-----------|----------|
| 403 Forbidden in browser | Cloud Run requires Bearer token; browsers don't send it | IAP handles OAuth login and injects token automatically |
| Proxy dies with Cloud Shell disconnect | `gcloud run services proxy` is ephemeral | IAP replaces proxy — direct URL access |
| Org policy blocks `allUsers` | Google org policy `iam.allowedPolicyMemberDomains` | Use `--no-allow-unauthenticated` + IAP (never needs `allUsers`) |
| Streamlit WebSocket disconnects | Load balancer routes WS to different instances | `--session-affinity` flag on Cloud Run deploy |
| Streamlit CORS/XSRF errors behind proxy | Streamlit blocks cross-origin requests by default | `.streamlit/config.toml` with `enableCORS=false`, `enableXsrfProtection=false` baked into Docker image |
| Cold start delays (~10-30s) | `min-instances=0` scales to zero | Set `--min-instances=1` if unacceptable (~$50/mo) |
| Output files not persisting | Default Cloud Run filesystem is ephemeral | GCS FUSE volume mount at `/app/ui_output` (requires gen2 execution environment) |
| Secret rotation not picked up | Running containers cache secret values | Redeploy after rotating secrets in Secret Manager |
| Cloud Build storage permission errors | Cloud Build SA / Compute SA lack `storage.objectAdmin` | `setup_and_deploy.sh` Step 4 grants permissions |
| IAP disabled after plain `gcloud run deploy` | `--iap` flag must be on every deploy | Both deploy scripts use `gcloud beta run deploy --iap` |

---

## 8. Local Development (Cloudtop)

### Environment Setup

```bash
# Install Python 3.12 (if not present)
python3.12 --version 2>/dev/null || {
  curl https://pyenv.run | bash
  echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
  echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
  echo 'eval "$(pyenv init -)"' >> ~/.bashrc
  source ~/.bashrc
  pyenv install 3.12
  pyenv global 3.12
}

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Clone and install
git clone https://github.com/nehilsood-cloudsufi/poc-auto-schematization.git
cd poc-auto-schematization
git checkout release/nehil/agentB_google_deploy
uv sync --all-extras
source .venv/bin/activate

# Authenticate
gcloud auth login --no-browser
gcloud auth application-default login --no-browser
gcloud config set project datcom-infosys-dev
```

### Create .env File

```bash
cat > .env << 'EOF'
GOOGLE_API_KEY=your-gemini-api-key-here
DC_API_KEY=your-dc-api-key-here
GOOGLE_SHEET_ID=your-sheet-id-here
EOF
chmod 600 .env
```

**Never commit `.env` to git.** It's already in `.gitignore`.

### Run Streamlit Locally

```bash
source .venv/bin/activate
export PYTHONPATH="$(pwd):$(pwd)/src"
streamlit run src/ui/app.py --server.port=8080
```

Access from Chromebook:
- **Remote Desktop:** Open `http://localhost:8080` in Cloudtop's browser
- **SSH with port forwarding:** `gcloud compute ssh CLOUDTOP_NAME -- -L 8080:localhost:8080`, then open `http://localhost:8080` in Chrome
- **VS Code Remote-SSH:** Auto-detects the port and offers to forward it

### Run Tests

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q
```

### Proxy Fixes (if needed)

If you see SSL/connection errors on Cloudtop:

```bash
export http_proxy="http://proxy.corp.google.com:3128"
export https_proxy="http://proxy.corp.google.com:3128"
export no_proxy="localhost,127.0.0.1,metadata.google.internal,*.googleapis.com"
```

---

## 9. Cloud Shell Quick Start

For users without Cloudtop — deploy from the browser, then access the app via its URL.

### Open Cloud Shell

1. Open https://console.cloud.google.com in Chrome
2. Set project to **`datcom-infosys-dev`** (project dropdown, top-left)
3. Click the **Cloud Shell** icon (terminal icon, top-right)

### Deploy

```bash
gcloud config set project datcom-infosys-dev

git clone https://github.com/nehilsood-cloudsufi/poc-auto-schematization.git
cd poc-auto-schematization
git checkout release/nehil/agentB_google_deploy

./deploy_google/setup_and_deploy.sh
```

### Access

After deploy completes, copy the URL from the output and open it in your browser. Google login handles the rest.

### Cloud Shell Facts

| Feature | Detail |
|---------|--------|
| Pre-installed tools | `gcloud`, `git`, `docker`, `python3` |
| Authentication | Automatic — uses your Google login |
| Persistent storage | 5 GB home directory (survives restarts) |
| Session timeout | ~20 min idle (reconnect anytime, files persist) |
| Cost | Free |

---

## 10. Troubleshooting

### Quick Diagnosis

Run the diagnostic script:

```bash
./deploy_google/diagnose.sh
```

This checks: health endpoint, revision status, IAM policy, and recent warning/error logs. Paste the output to get help.

### Common Issues

#### 403 Forbidden after deploy

```bash
# Re-enable IAP
./deploy_google/setup_iap.sh
# Wait 1-2 minutes for propagation, then refresh
```

#### PERMISSION_DENIED during deploy

```bash
# Check which roles are missing
./deploy_google/permission_check.sh
# Send the output to your manager
```

#### Cloud Build fails

```bash
# Check recent builds
gcloud builds list --limit=3

# View build logs
gcloud builds log $(gcloud builds list --limit=1 --format='value(id)')
```

Common causes:
- **Storage permission error:** Re-run `./deploy_google/setup_and_deploy.sh` (Step 4 fixes permissions)
- **Timeout:** Check `.gcloudignore` is present and not uploading unnecessary files
- **Large context:** First build can take up to 20 min

#### Container crashes on startup

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND severity>=ERROR' \
  --project=datcom-infosys-dev --limit=20
```

Common causes:
- **Missing secret:** `gcloud secrets list`
- **ModuleNotFoundError:** Check `.gcloudignore` is not excluding `src/` directories

#### Output files not persisting (GCS empty)

```bash
# Verify gen2 execution environment
gcloud run services describe auto-schematization --region=europe-west1 \
  --format='value(spec.template.metadata.annotations["run.googleapis.com/execution-environment"])'
# Must show: gen2
```

#### Streamlit WebSocket disconnects

```bash
# Verify session affinity
gcloud run services describe auto-schematization --region=europe-west1 \
  --format='value(spec.template.metadata.annotations["run.googleapis.com/sessionAffinity"])'
# Must show: true
```

#### Google Sheets 403 error

Share the sheet with the Cloud Run service account as Editor:

```bash
PROJECT_NUMBER=$(gcloud projects describe datcom-infosys-dev --format='value(projectNumber)')
echo "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
```

#### Updating a Secret

```bash
echo -n "new-api-key" | gcloud secrets versions add GOOGLE_API_KEY --data-file=-
# Must redeploy to pick up new secret:
./deploy_google/deploy_cloudtop.sh
```

---

## 11. Script Reference

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `setup_and_deploy.sh` | Full setup + deploy (8 steps) | First-time deployment, recreating infrastructure |
| `deploy_cloudtop.sh` | Quick rebuild + deploy (3 steps) | After code changes (~2-3 min) |
| `setup_iap.sh` | Enable/re-enable IAP | If 403 persists after deploy |
| `diagnose.sh` | Service health, revisions, logs, IAM | Debugging any issue |
| `permission_check.sh` | Verify IAM roles | Before asking manager for access |

All scripts accept `[PROJECT_ID] [REGION]` as optional positional arguments, defaulting to `datcom-infosys-dev` and `europe-west1`.

---

## 12. Configuration Reference

### Cloud Run Settings

| Setting | Value | Why |
|---------|-------|-----|
| CPU | 2 vCPU | Pipeline is CPU-intensive |
| Memory | 4 GiB | Large CSV processing |
| Timeout | 3600s (1 hour) | Pipeline runs can be long |
| Concurrency | 80 | Streamlit handles multiple users |
| Min instances | 0 | Cost savings (set to 1 to avoid cold starts, ~$50/mo) |
| Max instances | 3 | Limits cost |
| Session affinity | true | Required for Streamlit WebSocket |
| Execution environment | gen2 | Required for GCS FUSE volume mount |
| IAP | enabled | Browser access via Google OAuth |
| Ingress | all | Required for IAP to work |

### Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `PYTHONPATH` | `/app:/app/src` | Import resolution |
| `UI_OUTPUT_DIR` | `/app/ui_output` | Output directory (GCS FUSE mount point) |
| `GCS_BUCKET` | `datcom-infosys-dev-agent-b-output` | Bucket name for app logic |

### Secrets (from Secret Manager)

| Secret | Purpose |
|--------|---------|
| `GOOGLE_API_KEY` | Gemini API key |
| `DC_API_KEY` | Data Commons API key |
| `GOOGLE_SHEET_ID` | Google Sheet ID for feedback (optional) |

### Docker / Streamlit Config

The Docker image bakes in `.streamlit/config.toml`:

```toml
[server]
enableCORS = false
enableXsrfProtection = false
```

This is required for Streamlit to work behind Cloud Run's load balancer and IAP. Without it, you'll see CORS/XSRF errors.
