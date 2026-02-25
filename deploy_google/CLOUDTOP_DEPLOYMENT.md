# Cloudtop Deployment Guide

> **Audience:** xw@ (external workforce) with Cloudtop access, wanting a full development environment (local Streamlit, tests, code editing) on `datcom-infosys-dev` / `europe-west1`.
>
> **Branch:** `release/nehil/agentB_google_deploy`
>
> **Don't have Cloudtop access?** Use [CLOUDSHELL_DEPLOYMENT.md](./CLOUDSHELL_DEPLOYMENT.md) instead — zero setup, browser-based.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Access Cloudtop from Your Chromebook](#2-access-cloudtop-from-your-chromebook)
3. [Cloudtop Environment Setup](#3-cloudtop-environment-setup)
4. [Clone and Install the Project](#4-clone-and-install-the-project)
5. [GCP Infrastructure Creation](#5-gcp-infrastructure-creation)
6. [Deploy to Cloud Run](#6-deploy-to-cloud-run)
7. [Run Streamlit Locally on Cloudtop](#7-run-streamlit-locally-on-cloudtop)
8. [Run Tests](#8-run-tests)
9. [Daily Workflow Quick Reference](#9-daily-workflow-quick-reference)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

- Your xw@ account must have a **Cloudtop instance provisioned** (ask your manager)
- You must be on the **Google corporate network** (office Wi-Fi, Ethernet, or VPN/BeyondCorp)
- IAM roles on `datcom-infosys-dev` (see [CLOUDSHELL_DEPLOYMENT.md Section 2](./CLOUDSHELL_DEPLOYMENT.md#2-get-gcp-access-ask-your-manager) for the full IAM request template)

### If You Don't Have Cloudtop Yet

Send this to your manager:

> Hi, I need a Cloudtop instance provisioned for my xw@ account (`YOUR_EMAIL`). I'll be using it for Auto-Schematization development and Cloud Run deployment. Standard config (4+ vCPU, 16+ GB RAM) should be fine.

Once provisioned, it typically takes 5-10 minutes for the VM to be ready.

### 403 Forbidden on cloudtop.corp.google.com

If you get a 403, your xw@ account isn't in the Cloudtop access group yet. Ask your manager to add you. Use [Cloud Shell](./CLOUDSHELL_DEPLOYMENT.md) in the meantime.

---

## 2. Access Cloudtop from Your Chromebook

### Option A: Remote Desktop (Easiest)

1. Open **https://cloudtop.corp.google.com** in Chrome
2. Sign in with your Google corporate account (xw@ or @google.com)
3. Click your Cloudtop instance name to launch the remote desktop
4. A new browser tab opens with the full Linux desktop

> **Tip:** Copy-paste works between Chromebook and the remote desktop. Use `Ctrl+C` / `Ctrl+V` as normal.

### Option B: SSH via Crostini

Chromebooks have a built-in Linux environment (Crostini). Enable it first:

1. Go to **Settings > Advanced > Developers**
2. Click **Turn on** next to "Linux development environment"
3. Follow the prompts (~2 minutes)
4. A **Terminal** app appears in your app drawer

Then install gcloud and SSH in:

```bash
# In Crostini terminal — install gcloud CLI (one-time)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate
gcloud auth login --no-browser
# Prints a URL — open it in Chrome, sign in, paste the code back

# SSH into Cloudtop with port forwarding (for Streamlit access)
gcloud compute ssh CLOUDTOP_NAME -- -L 8080:localhost:8080
```

> **Note:** Crostini shares localhost with Chrome, so `http://localhost:8080` opens in your Chromebook browser after port forwarding.

### Option C: VS Code Remote-SSH (Best for Development)

1. Install VS Code in Crostini: download `.deb` from [code.visualstudio.com](https://code.visualstudio.com/), open it — ChromeOS installs it automatically
2. Install the **Remote - SSH** extension (by Microsoft)
3. `Ctrl+Shift+P` → "Remote-SSH: Connect to Host" → `CLOUDTOP_NAME.c.googlers.com`
4. VS Code opens a new window connected to Cloudtop
5. Open the project folder: `~/poc-auto-schematization`

> **Tip:** VS Code Remote-SSH automatically handles port forwarding. When Streamlit starts on port 8080, VS Code detects it and offers to open it in Chrome.

### Finding Your Cloudtop Instance Name

```bash
# From Crostini terminal or Cloudtop
gcloud compute instances list --filter="name~cloudtop"

# Or check https://cloudtop.corp.google.com
```

---

## 3. Cloudtop Environment Setup

All commands below run **on Cloudtop** (via Remote Desktop terminal, SSH, or VS Code terminal).

### 3.1 Verify Base Tools

```bash
gcloud version          # Google Cloud SDK (pre-installed)
git --version           # Git (pre-installed)
python3 --version       # System Python (may be 3.9 or 3.11)
```

### 3.2 Install Python 3.12

```bash
python3.12 --version 2>/dev/null || {
  curl https://pyenv.run | bash

  # Add to ~/.bashrc
  echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
  echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
  echo 'eval "$(pyenv init -)"' >> ~/.bashrc
  source ~/.bashrc

  pyenv install 3.12
  pyenv global 3.12
}

python3 --version   # Should show 3.12.x
```

### 3.3 Install uv (Python Package Manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

uv --version
```

### 3.4 Authenticate with GCP

```bash
gcloud auth login --no-browser
gcloud auth application-default login --no-browser

gcloud config set project datcom-infosys-dev
gcloud config set run/region europe-west1
```

### 3.5 Proxy Fixes (if needed)

If you see SSL/connection errors on Cloudtop:

```bash
export http_proxy="http://proxy.corp.google.com:3128"
export https_proxy="http://proxy.corp.google.com:3128"
export no_proxy="localhost,127.0.0.1,metadata.google.internal,*.googleapis.com"
```

Add to `~/.bashrc` if persistent.

---

## 4. Clone and Install the Project

```bash
cd ~
git clone https://github.com/nehilsood-cloudsufi/poc-auto-schematization.git
cd poc-auto-schematization
git checkout release/nehil/agentB_google_deploy

# Install all dependencies
uv sync --all-extras
source .venv/bin/activate

# Verify key packages
python -c "import streamlit; print('Streamlit', streamlit.__version__)"
python -c "import google.genai; print('google-genai OK')"
```

### Create .env File

```bash
cat > .env << 'EOF'
# Required: Gemini API key (get from https://aistudio.google.com/apikey)
GOOGLE_API_KEY=your-gemini-api-key-here

# Required: Data Commons API key (get from https://apikeys.datacommons.org)
DC_API_KEY=your-dc-api-key-here

# Optional: Google Sheet ID for developer feedback
GOOGLE_SHEET_ID=your-sheet-id-here
EOF

chmod 600 .env
```

**Never commit `.env` to git.** It's already in `.gitignore`.

---

## 5. GCP Infrastructure Creation

Run the permission check, then the infrastructure setup (one-time):

```bash
cd ~/poc-auto-schematization

# Check permissions
chmod +x deploy_google/permission_check.sh
./deploy_google/permission_check.sh

# Create all infrastructure (APIs, Artifact Registry, secrets, GCS bucket)
chmod +x deploy_google/infra_setup.sh
./deploy_google/infra_setup.sh
```

The script is idempotent (safe to re-run) and will prompt you for API keys interactively. See [CLOUDSHELL_DEPLOYMENT.md Section 4](./CLOUDSHELL_DEPLOYMENT.md#4-gcp-infrastructure-creation) for details.

---

## 6. Deploy to Cloud Run

```bash
cd ~/poc-auto-schematization
git pull origin release/nehil/agentB_google_deploy

chmod +x deploy_google/deploy_cloudtop.sh
./deploy_google/deploy_cloudtop.sh
```

Defaults: project=`datcom-infosys-dev`, region=`europe-west1`.

> **Note:** The existing `deploy/deploy.sh` is for CloudSufi (`us-central1`). Use `deploy_google/deploy_cloudtop.sh` for Google-side deployment.

**First build: ~5-8 min.** Subsequent deploys: ~2-3 min.

### Get the URL

```bash
gcloud run services describe auto-schematization --region=europe-west1 --format='value(status.url)'
```

### Access the Deployed App

Open the Cloud Run URL directly in your browser — IAP handles Google login automatically.

```bash
# Get the URL
gcloud run services describe auto-schematization --region=europe-west1 --format='value(status.url)'
```

> If you see 403 after first deploy, run `./deploy_google/setup_iap.sh` and wait 1-2 minutes.

### Post-Deploy Verification

See [CLOUDSHELL_DEPLOYMENT.md Section 6](./CLOUDSHELL_DEPLOYMENT.md#6-post-deploy-verification) for the full verification checklist.

---

## 7. Run Streamlit Locally on Cloudtop

This is the main advantage of Cloudtop over Cloud Shell — you can run the full app locally for development and testing.

```bash
cd ~/poc-auto-schematization
source .venv/bin/activate
export PYTHONPATH="$(pwd):$(pwd)/src"

streamlit run src/ui/app.py --server.port=8080
```

**Access from your Chromebook:**

- **Remote Desktop:** Open `http://localhost:8080` in the Cloudtop's browser
- **SSH:** Make sure you connected with `-L 8080:localhost:8080`, then open `http://localhost:8080` in Chrome on your Chromebook
- **VS Code:** It auto-detects the port and offers to forward it

---

## 8. Run Tests

```bash
cd ~/poc-auto-schematization
source .venv/bin/activate

PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q
```

---

## 9. Daily Workflow Quick Reference

```bash
# === Morning Setup (on Cloudtop) ===
cd ~/poc-auto-schematization
source .venv/bin/activate
export PYTHONPATH="$(pwd):$(pwd)/src"
export PROJECT_ID="datcom-infosys-dev"
export REGION="europe-west1"

# === Pull latest code ===
git pull origin release/nehil/agentB_google_deploy

# === Local dev ===
streamlit run src/ui/app.py --server.port=8080     # Run locally
pytest tests/ -x -q                                  # Run tests

# === Deploy to Cloud Run ===
./deploy_google/deploy_cloudtop.sh

# === Access deployed app via proxy ===
gcloud run services proxy auto-schematization --region=$REGION --port=9090
# Open http://localhost:9090 in browser

# === Health check ===
curl -sf -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  $(gcloud run services describe auto-schematization --region=$REGION --format='value(status.url)')/_stcore/health

# === View logs ===
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="auto-schematization"' \
  --project=$PROJECT_ID --limit=20 --format="table(timestamp,jsonPayload.message)"

# === View output files ===
gcloud storage ls gs://${PROJECT_ID}-agent-b-output/ --recursive
```

> **Tip:** Use `tmux new -s dev` so your processes survive SSH disconnects.

---

## 10. Troubleshooting

### 403 Forbidden on cloudtop.corp.google.com

Your xw@ account isn't in the Cloudtop access group. Ask your manager to add you. Use [Cloud Shell](./CLOUDSHELL_DEPLOYMENT.md) in the meantime.

### Proxy errors (SSL, connection refused)

```bash
export http_proxy="http://proxy.corp.google.com:3128"
export https_proxy="http://proxy.corp.google.com:3128"
export no_proxy="localhost,127.0.0.1,metadata.google.internal,*.googleapis.com"
```

### Can't open localhost:8080 from Chromebook

Make sure you SSH'd with port forwarding:

```bash
gcloud compute ssh CLOUDTOP_NAME -- -L 8080:localhost:8080
```

Or use Remote Desktop and open the browser on Cloudtop itself.

### "PERMISSION_DENIED" during deploy

Run `./deploy_google/permission_check.sh` to identify the missing role.

### For all other Cloud Run issues

See [CLOUDSHELL_DEPLOYMENT.md Section 8](./CLOUDSHELL_DEPLOYMENT.md#8-troubleshooting) — covers Cloud Build failures, container crashes, ModuleNotFoundError, Sheets 403, GCS persistence, WebSocket disconnects.

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
