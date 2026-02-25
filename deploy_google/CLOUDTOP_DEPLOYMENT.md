# Cloudtop Deployment Guide

> **Audience:** xw@ (external workforce) deploying Agent B on a Google Cloudtop VM for the first time.
>
> **Branch:** `release/nehil/agentB_google_deploy`

---

## Table of Contents

0. [Accessing Cloudtop from Your Laptop](#0-accessing-cloudtop-from-your-laptop)
1. [Get GCP Access (Ask Your Manager)](#1-get-gcp-access-ask-your-manager)
2. [Permission Self-Check](#2-permission-self-check)
3. [Cloudtop Environment Setup](#3-cloudtop-environment-setup)
4. [Local Development Setup](#4-local-development-setup)
5. [GCP Infrastructure Creation](#5-gcp-infrastructure-creation)
6. [Deploy to Cloud Run](#6-deploy-to-cloud-run)
7. [Post-Deploy Verification](#7-post-deploy-verification)
8. [Troubleshooting](#8-troubleshooting)
9. [Daily Workflow Quick Reference](#9-daily-workflow-quick-reference)
10. [CloudSufi vs Cloudtop Comparison](#10-cloudsufi-vs-cloudtop-comparison)

---

## 0. Accessing Cloudtop from Your Chromebook

Cloudtop is a Google-managed Linux VM that you access remotely from your Chromebook. There are three ways to connect.

### Prerequisites

- You must be on the **Google corporate network** (office Wi-Fi, Ethernet, or VPN/BeyondCorp)
- Your xw@ account must have a Cloudtop instance provisioned (ask your manager if you don't have one yet)

### Option A: Remote Desktop via Chrome (Recommended for First-Time Setup)

This is the easiest option on a Chromebook — everything runs in the browser.

1. Open Chrome on your Chromebook
2. Go to **https://cloudtop.corp.google.com**
3. Sign in with your Google corporate account (xw@ or @google.com)
4. Click your Cloudtop instance name to launch the remote desktop
5. A new browser tab opens with the full Linux desktop

> **Tip:** Copy-paste works between Chromebook and the remote desktop. Use `Ctrl+C` / `Ctrl+V` as normal.

### Option B: SSH via Linux Terminal (Recommended for Daily Use)

Chromebooks have a built-in Linux development environment (Crostini). Enable it first, then use SSH.

**Enable Linux on your Chromebook (one-time setup):**

1. Go to **Settings > Advanced > Developers**
2. Click **Turn on** next to "Linux development environment"
3. Follow the prompts (takes ~2 minutes to install)
4. A **Terminal** app appears in your app drawer

**Install gcloud CLI and connect:**

```bash
# Open the Terminal app on your Chromebook

# 1. Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL   # Restart shell to pick up PATH changes

# 2. Authenticate
gcloud auth login --no-browser
# This prints a URL — open it in Chrome, sign in, paste the code back

# 3. SSH into your Cloudtop
# Replace CLOUDTOP_NAME with your instance name (e.g., "nehil")
gcloud compute ssh CLOUDTOP_NAME

# Or if you know the full hostname:
ssh CLOUDTOP_NAME.c.googlers.com
```

**Port forwarding** (needed to access Streamlit running on Cloudtop):

```bash
# Forward Cloudtop port 8080 to your Chromebook's localhost:8080
gcloud compute ssh CLOUDTOP_NAME -- -L 8080:localhost:8080

# Then open http://localhost:8080 in Chrome on your Chromebook
```

> **Note:** The Linux terminal on Chromebook shares localhost with Chrome, so port forwarding works seamlessly — just open `http://localhost:8080` in your browser.

### Option C: VS Code via Crostini (Best for Development)

You can install VS Code in the Linux environment and use Remote-SSH to connect to Cloudtop.

1. Enable Linux (see Option B above)
2. Download VS Code `.deb` from [code.visualstudio.com](https://code.visualstudio.com/)
3. Open the `.deb` file — ChromeOS installs it automatically into Linux
4. Launch **Visual Studio Code** from the app drawer
5. Install the **Remote - SSH** extension (by Microsoft)
6. Press `Ctrl+Shift+P` → type "Remote-SSH: Connect to Host"
7. Enter your Cloudtop hostname: `CLOUDTOP_NAME.c.googlers.com`
8. VS Code opens a new window connected to Cloudtop
9. Open the project folder: `~/poc-auto-schematization`

> **Tip:** VS Code Remote-SSH automatically handles port forwarding. When Streamlit starts on port 8080, VS Code detects it and offers to open it in Chrome.

### Finding Your Cloudtop Instance Name

From the Cloudtop web UI or from the Linux terminal:

```bash
# From the Linux terminal (after gcloud is installed)
gcloud compute instances list --filter="name~cloudtop"

# Or just check https://cloudtop.corp.google.com for your instance name
```

### If You Don't Have a Cloudtop Yet

Send this to your manager:

> Hi, I need a Cloudtop instance provisioned for my xw@ account (`YOUR_EMAIL`). I'll be using it for Agent B development and Cloud Run deployment. Standard config (4+ vCPU, 16+ GB RAM) should be fine.

Once provisioned, it typically takes 5-10 minutes for the VM to be ready.

---

## 1. Get GCP Access (Ask Your Manager)

Before anything else, you need a GCP project and IAM roles. Copy-paste this message to your manager (or TL) and send it via Chat/email:

> **Subject: GCP project + IAM roles needed for Agent B deployment**
>
> Hi [Manager],
>
> I need access to the GCP project **`datcom-infosys-dev`** (or a new project) to deploy the Agent B (Auto-Schematization) Streamlit app to Cloud Run.
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

**Wait for your manager's reply before proceeding.** You need the IAM roles granted on `datcom-infosys-dev`.

---

## 2. Permission Self-Check

After your manager says "done," run this script to verify every required permission **before** attempting the actual setup. Save it or run commands one by one:

```bash
# ============================================================
# PERMISSION SELF-CHECK SCRIPT
# Run AFTER your manager grants access
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
echo "If any check shows PERMISSION_DENIED, ask your manager to grant the corresponding role (see table in Step 1)."
```

**If any check fails**, reply to your manager with:

> Check #N failed with PERMISSION_DENIED. Could you grant me `roles/xxx` on project `PROJECT_ID`?

---

## 3. Cloudtop Environment Setup

Cloudtop VMs come with some tools pre-installed, but you'll need Python 3.12 and `uv`.

### 3.1 Verify Base Tools

```bash
# These should already be available on Cloudtop
gcloud version          # Google Cloud SDK
git --version           # Git
python3 --version       # System Python (may be 3.9 or 3.11)
```

### 3.2 Install Python 3.12

Cloudtop's default Python may be older. Check and install if needed:

```bash
python3.12 --version 2>/dev/null || echo "Need to install Python 3.12"

# If not available, install via pyenv (recommended on Cloudtop)
curl https://pyenv.run | bash

# Add to shell (add these to ~/.bashrc if not already there)
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Install Python 3.12
pyenv install 3.12
pyenv global 3.12

# Verify
python3 --version   # Should show 3.12.x
```

### 3.3 Install uv (Python Package Manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (installer usually does this, but verify)
export PATH="$HOME/.local/bin:$PATH"

uv --version
```

### 3.4 Proxy Fixes (Cloudtop-specific)

Cloudtop VMs may route traffic through a corporate proxy. If you see SSL/connection errors:

```bash
# Check if proxy is set
echo $http_proxy
echo $https_proxy

# If proxy is configured but causing issues with gcloud/pip, try:
# Option A: Use the proxy (usually works)
export http_proxy="http://proxy.corp.google.com:3128"
export https_proxy="http://proxy.corp.google.com:3128"
export no_proxy="localhost,127.0.0.1,metadata.google.internal,*.googleapis.com"

# Option B: If gcloud auth uses browser flow and you're on Cloudtop:
gcloud auth login --no-browser
# This gives you a URL to paste in your local browser
```

### 3.5 Authenticate with GCP

```bash
gcloud auth login              # Interactive login (use --no-browser on Cloudtop)
gcloud auth application-default login   # For application-default credentials

gcloud config set project "$PROJECT_ID"
gcloud config set run/region europe-west1
```

---

## 4. Local Development Setup

### 4.1 Clone the Repository

```bash
cd ~
git clone https://github.com/anthropics/poc-auto-schematization.git
cd poc-auto-schematization

# Switch to the deployment branch
git checkout release/nehil/agentB_google_deploy
git pull origin release/nehil/agentB_google_deploy
```

### 4.2 Install Dependencies

```bash
# Create virtual environment and install all deps
uv sync --all-extras

# Activate the virtual environment
source .venv/bin/activate

# Verify key packages
python -c "import streamlit; print('Streamlit', streamlit.__version__)"
python -c "import google.genai; print('google-genai OK')"
```

### 4.3 Create .env File

```bash
cat > .env << 'EOF'
# Required: Gemini API key (get from https://aistudio.google.com/apikey)
GOOGLE_API_KEY=your-gemini-api-key-here

# Required: Data Commons API key (get from https://apikeys.datacommons.org)
DC_API_KEY=your-dc-api-key-here

# Optional: Google Sheet ID for developer feedback
GOOGLE_SHEET_ID=your-sheet-id-here
EOF

# Protect the file
chmod 600 .env
```

**Never commit `.env` to git.** It's already in `.gitignore`.

### 4.4 Run Streamlit Locally (Verify It Works)

```bash
export PYTHONPATH="$(pwd):$(pwd)/src"

streamlit run src/ui/app.py --server.port=8080
```

If on Cloudtop and you can't open a browser, use SSH port forwarding from your local machine:

```bash
# On your LOCAL machine (not Cloudtop), forward port 8080:
gcloud compute ssh YOUR_CLOUDTOP_NAME -- -L 8080:localhost:8080

# Then open http://localhost:8080 in your local browser
```

### 4.5 Run Tests (Sanity Check)

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q --timeout=60
```

---

## 5. GCP Infrastructure Creation

These commands create all the GCP resources needed for Cloud Run deployment.

### 5.1 Set Variables

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

### 5.2 Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com
```

This takes ~30 seconds. You only need to do this once per project.

### 5.3 Create Artifact Registry Repository

```bash
gcloud artifacts repositories create agent-b \
  --repository-format=docker \
  --location=$REGION \
  --description="Agent B container images"
```

### 5.4 Create Secrets in Secret Manager

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

### 5.5 Create GCS Output Bucket

```bash
gcloud storage buckets create gs://${BUCKET} \
  --location=$REGION \
  --uniform-bucket-level-access

gcloud storage buckets add-iam-policy-binding gs://${BUCKET} \
  --member="serviceAccount:${SA}" --role="roles/storage.objectAdmin"
```

### 5.6 (Optional) Google Sheets Setup

If using the developer feedback feature:

1. Create a Google Sheet (or use an existing one)
2. Share it with the service account as **Editor**: copy the `$SA` email and add it as a sheet collaborator
3. Store the Sheet ID in Secret Manager (done in 5.4 above)

---

## 6. Deploy to Cloud Run

### 6.1 One-Command Deploy

```bash
cd ~/poc-auto-schematization

chmod +x deploy_google/deploy_cloudtop.sh
./deploy_google/deploy_cloudtop.sh
```

Defaults: project=`datcom-infosys-dev`, region=`europe-west1`. Override with positional args:

```bash
./deploy_google/deploy_cloudtop.sh my-other-project europe-west4
```

> **Note:** The existing `deploy/deploy.sh` is for CloudSufi (`us-central1`). Use `deploy_google/deploy_cloudtop.sh` for Google-side deployment.

**First build takes ~5-8 minutes** (Docker image build + push). Subsequent deploys are faster (~2-3 min) due to layer caching.

### 6.2 What the Deploy Script Does

1. **`gcloud builds submit`** — Sends the repo to Cloud Build, which builds the Docker image and pushes it to Artifact Registry
2. **`gcloud run deploy`** — Creates/updates the Cloud Run service with:
   - 2 vCPU, 4 GB memory
   - 1-hour request timeout
   - Session affinity (required for Streamlit WebSocket)
   - GCS FUSE volume mount at `/app/ui_output`
   - Secrets injected as env vars from Secret Manager
   - Public access (no authentication)

### 6.3 Get the URL

After deploy completes, the script prints the URL. You can also retrieve it:

```bash
gcloud run services describe agent-b --region=$REGION --format='value(status.url)'
```

---

## 7. Post-Deploy Verification

Run these checks after deployment:

```bash
# 1. Get the service URL
URL=$(gcloud run services describe agent-b --region=$REGION --format='value(status.url)')
echo "Service URL: $URL"

# 2. Health check
curl -sf "${URL}/_stcore/health"
# Expected: "ok"

# 3. Open in browser (from your local machine, not Cloudtop)
echo "Open this in your browser: $URL"

# 4. Check Cloud Run logs for startup
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="agent-b"' \
  --project=$PROJECT_ID --limit=20 --format="table(timestamp,jsonPayload.message)"

# 5. Check MCP server started
gcloud logging read \
  'resource.type="cloud_run_revision" AND jsonPayload.message:"MCP"' \
  --project=$PROJECT_ID --limit=5

# 6. Verify GCS bucket is accessible
gcloud storage ls gs://${BUCKET}/
# Expected: empty (no runs yet) or list of run directories
```

### Smoke Test

1. Open the URL in your browser
2. Upload a small CSV file (e.g., one from `input/bis_bis_central_bank_policy_rate/test_data/`)
3. Click "Run Pipeline"
4. Wait for completion (~2-5 min for a small dataset)
5. Check that output appears in GCS: `gcloud storage ls gs://${BUCKET}/ --recursive`

---

## 8. Troubleshooting

### "PERMISSION_DENIED" during deploy

Go back to [Section 2](#2-permission-self-check) and re-run the self-check. The failing check tells you exactly which role is missing.

### Cloud Build fails with "unable to resolve" or timeout

```bash
# Check build logs
gcloud builds list --limit=3
gcloud builds log $(gcloud builds list --limit=1 --format='value(id)')
```

Common causes:
- **Proxy issues:** Cloudtop may block Docker Hub. Cloud Build runs on Google infra, so this usually works, but check if `.gcloudignore` is excluding needed files.
- **Large context:** If the build uploads too much data, check `.gcloudignore` is present and correct.

### Container crashes on startup

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND severity>=ERROR' \
  --project=$PROJECT_ID --limit=20
```

Common causes:
- **Missing secret:** Verify all three secrets exist: `gcloud secrets list`
- **Secret binding missing:** The SA needs `secretAccessor` on each secret (see 5.4)
- **MCP binary missing:** Check that `datacommons-mcp` is in `requirements.txt`

### "ModuleNotFoundError" in Cloud Run

The `.gcloudignore` file controls what gets uploaded to Cloud Build. If `src/data_commons/schema/` is excluded:

```bash
# Check .gcloudignore isn't too aggressive
cat .gcloudignore
# Ensure it does NOT exclude src/ directories
```

### Google Sheets 403 error

```
gspread.exceptions.APIError: [403]: The caller does not have permission
```

The Cloud Run service account needs Editor access on the Google Sheet:

```bash
echo $SA   # Copy this email
# Go to your Google Sheet → Share → Add this email as Editor
```

### Output files not persisting (GCS empty after run)

```bash
# 1. Check execution environment is gen2 (required for GCS FUSE)
gcloud run services describe agent-b --region=$REGION \
  --format='value(spec.template.metadata.annotations["run.googleapis.com/execution-environment"])'
# Must show: gen2

# 2. Check SA has storage access
gcloud storage buckets get-iam-policy gs://${BUCKET} \
  --format='table(bindings.role,bindings.members)'
```

### Streamlit WebSocket disconnects

If the UI loads but then disconnects, session affinity may be off:

```bash
gcloud run services describe agent-b --region=$REGION \
  --format='value(spec.template.metadata.annotations["run.googleapis.com/sessionAffinity"])'
# Must show: true
```

### Redeploying After Code Changes

```bash
cd ~/poc-auto-schematization
git pull origin release/nehil/agentB_google_deploy

# If dependencies changed:
uv sync --all-extras
uv pip freeze > requirements.txt

# Redeploy
./deploy_google/deploy_cloudtop.sh
```

---

## 9. Daily Workflow Quick Reference

```bash
# === Morning Setup ===
cd ~/poc-auto-schematization
source .venv/bin/activate
export PYTHONPATH="$(pwd):$(pwd)/src"
export PROJECT_ID="datcom-infosys-dev"
export REGION="europe-west1"

# === Local Dev ===
streamlit run src/ui/app.py --server.port=8080     # Run locally
pytest tests/ -x -q                                  # Run tests

# === Deploy ===
./deploy_google/deploy_cloudtop.sh

# === Check Status ===
URL=$(gcloud run services describe agent-b --region=$REGION --format='value(status.url)')
curl -sf "${URL}/_stcore/health"                      # Health check

# === View Logs ===
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="agent-b"' \
  --project=$PROJECT_ID --limit=20 --format="table(timestamp,jsonPayload.message)"

# === View Output ===
gcloud storage ls gs://${PROJECT_ID}-agent-b-output/ --recursive

# === Update a Secret ===
echo -n "new-api-key" | gcloud secrets versions add GOOGLE_API_KEY --data-file=-
# Then redeploy
./deploy_google/deploy_cloudtop.sh
```

---

## 10. Chromebook + Cloudtop vs CloudSufi Comparison

| Aspect | CloudSufi (Mac) | Chromebook + Cloudtop |
|--------|-----------------|----------------------|
| **Local OS** | macOS | ChromeOS |
| **Dev environment** | Local machine | Cloudtop VM (remote Linux) |
| **Access to Cloudtop** | SSH / Remote Desktop | Chrome browser / Crostini SSH / VS Code |
| **Python** | Homebrew / pyenv | Installed on Cloudtop (pyenv) |
| **Docker** | Docker Desktop (local) | Available on Cloudtop |
| **gcloud CLI** | `brew install google-cloud-sdk` | Install in Crostini or use on Cloudtop |
| **Browser access** | Direct `localhost:8080` | Port-forward via SSH, open in Chrome |
| **Proxy** | Usually none | May have corporate proxy on Cloudtop |
| **GCP Auth** | `gcloud auth login` (opens browser) | `gcloud auth login --no-browser` |
| **File editing** | VS Code local | VS Code via Crostini + Remote-SSH |
| **Git** | Standard (local) | Standard (on Cloudtop) |
| **Deploy script** | `deploy/deploy.sh` (us-central1) | `deploy_google/deploy_cloudtop.sh` (europe-west1) |
| **Key difference** | Everything runs locally | Chromebook is a thin client; all work happens on Cloudtop |

### Tips for Chromebook + Cloudtop

- **Enable Linux (Crostini)** on your Chromebook for SSH and VS Code — see [Section 0](#0-accessing-cloudtop-from-your-chromebook)
- **Remote Desktop is the easiest start** — just open `cloudtop.corp.google.com` in Chrome, no setup required
- **VS Code via Crostini + Remote-SSH** gives the best dev experience once set up
- **Port forwarding** works seamlessly — Crostini shares localhost with Chrome, so `http://localhost:8080` opens in your browser after SSH `-L 8080:localhost:8080`
- **Tmux/screen on Cloudtop** is recommended so your processes survive SSH disconnects: `tmux new -s dev`
- **Clipboard**: Copy-paste works natively in Remote Desktop. In Crostini terminal, use `Ctrl+Shift+C` / `Ctrl+Shift+V`
- **Storage**: Your Chromebook's local storage is limited — keep all code and data on Cloudtop, not locally

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
│  │ /app/ui_output ↔ gs://{PROJECT}-agent-b-output       │ │
│  └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   Secret Manager      Google Sheets API    Gemini API
   (API keys)          (feedback rows)      (LLM calls)
```

**Container startup sequence:**
1. `deploy/startup.sh` starts the DC MCP server on port 3000 in background
2. Waits up to 30s for MCP health check (`/health`)
3. `exec streamlit run` replaces shell as PID 1 (receives SIGTERM for graceful shutdown)
