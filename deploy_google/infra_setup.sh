#!/bin/bash
# ============================================================
# GCP Infrastructure Setup for Agent B (one-time)
# Creates: APIs, Artifact Registry, Secrets, GCS bucket
# Usage: ./deploy_google/infra_setup.sh [PROJECT_ID] [REGION]
# ============================================================

set -euo pipefail

PROJECT_ID="${1:-datcom-infosys-dev}"
REGION="${2:-europe-west1}"
BUCKET="${PROJECT_ID}-agent-b-output"

gcloud config set project "$PROJECT_ID" --quiet

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "=== Infrastructure Setup ==="
echo "  Project:         $PROJECT_ID"
echo "  Region:          $REGION"
echo "  Service Account: $SA"
echo "  GCS Bucket:      gs://$BUCKET"
echo ""

# --- 1. Enable APIs ---
echo ">>> Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com
echo "    Done."
echo ""

# --- 2. Artifact Registry ---
echo ">>> Creating Artifact Registry repository..."
if gcloud artifacts repositories describe agent-b --location="$REGION" &>/dev/null; then
  echo "    Already exists, skipping."
else
  gcloud artifacts repositories create agent-b \
    --repository-format=docker \
    --location="$REGION" \
    --description="Agent B container images"
  echo "    Created."
fi
echo ""

# --- 3. Secrets ---
create_secret() {
  local name="$1"
  local prompt="$2"

  if gcloud secrets describe "$name" &>/dev/null; then
    echo "    Secret '$name' already exists, skipping."
    return
  fi

  read -rp "    Enter $prompt: " value
  if [ -z "$value" ]; then
    echo "    Skipped (empty value)."
    return
  fi

  echo -n "$value" | gcloud secrets create "$name" --data-file=-
  gcloud secrets add-iam-policy-binding "$name" \
    --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor" --quiet
  echo "    Created and bound to SA."
}

echo ">>> Setting up secrets..."
create_secret "GOOGLE_API_KEY" "Gemini API key (from https://aistudio.google.com/apikey)"
create_secret "DC_API_KEY" "Data Commons API key (from https://apikeys.datacommons.org)"
create_secret "GOOGLE_SHEET_ID" "Google Sheet ID (optional, press Enter to skip)"
echo ""

# --- 4. GCS Bucket ---
echo ">>> Creating GCS bucket..."
if gcloud storage buckets describe "gs://${BUCKET}" &>/dev/null; then
  echo "    Already exists, skipping."
else
  gcloud storage buckets create "gs://${BUCKET}" \
    --location="$REGION" \
    --uniform-bucket-level-access
  echo "    Created."
fi

echo ">>> Granting SA storage access..."
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${SA}" --role="roles/storage.objectAdmin" --quiet
echo "    Done."
echo ""

# --- Summary ---
echo "==========================================="
echo "  INFRASTRUCTURE SETUP COMPLETE"
echo "==========================================="
echo ""
echo "  APIs:              Enabled"
echo "  Artifact Registry: europe-west1-docker.pkg.dev/$PROJECT_ID/agent-b"
echo "  Secrets:           $(gcloud secrets list --format='value(name)' | tr '\n' ', ')"
echo "  GCS Bucket:        gs://$BUCKET"
echo ""
echo "  Next step: ./deploy_google/deploy_cloudtop.sh"
