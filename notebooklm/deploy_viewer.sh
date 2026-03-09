#!/bin/bash
set -euo pipefail

PROJECT_ID="${1:-$(gcloud config get-value project)}"
REGION="${2:-us-central1}"
SERVICE="notebooklm-viewer"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/agent-b/${SERVICE}:latest"

echo "Deploying NotebookLM Viewer → ${PROJECT_ID} / ${REGION}"

# Ensure Artifact Registry repo exists
REPO="agent-b"
if ! gcloud artifacts repositories describe "$REPO" --location="$REGION" --project="$PROJECT_ID" &>/dev/null 2>&1; then
    echo "Creating Artifact Registry repo: $REPO"
    gcloud artifacts repositories create "$REPO" \
        --repository-format=docker --location="$REGION" --project="$PROJECT_ID" --quiet
fi

# Ensure secret exists
if ! gcloud secrets describe NOTEBOOKLM_STORAGE_STATE --project="$PROJECT_ID" &>/dev/null 2>&1; then
    echo ""
    echo "Secret NOTEBOOKLM_STORAGE_STATE not found."
    echo "1. On Chromebook Cloud Shell: notebooklm login"
    echo "2. Download storage_state.json from Cloud Shell"
    echo "3. Run: gcloud secrets create NOTEBOOKLM_STORAGE_STATE --data-file=storage_state.json --project=$PROJECT_ID"
    exit 1
fi

# Grant compute SA access to secret
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding NOTEBOOKLM_STORAGE_STATE \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="$PROJECT_ID" --quiet >/dev/null 2>&1 || true

# Build from notebooklm/ directory using the viewer Dockerfile
# gcloud builds submit doesn't support --dockerfile, so use a cloudbuild config
cat > /tmp/cloudbuild_viewer.yaml << CBEOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${IMAGE}', '-f', 'Dockerfile.viewer', '.']
images:
  - '${IMAGE}'
timeout: 900s
CBEOF

gcloud builds submit \
    --config=/tmp/cloudbuild_viewer.yaml \
    --project "${PROJECT_ID}" \
    .

# Deploy
gcloud run deploy "${SERVICE}" \
    --image "${IMAGE}" \
    --platform managed \
    --region "${REGION}" \
    --allow-unauthenticated \
    --port 8080 \
    --cpu 1 \
    --memory 2Gi \
    --timeout 300 \
    --concurrency 10 \
    --min-instances 0 \
    --max-instances 2 \
    --session-affinity \
    --set-secrets "NOTEBOOKLM_STORAGE_STATE=NOTEBOOKLM_STORAGE_STATE:latest,NOTEBOOKLM_AUTH_JSON=NOTEBOOKLM_STORAGE_STATE:latest"

URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --format='value(status.url)')
echo "Deployed! URL: ${URL}"
