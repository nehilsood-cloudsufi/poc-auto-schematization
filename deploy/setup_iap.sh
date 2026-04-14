#!/bin/bash
set -euo pipefail

# Setup Identity-Aware Proxy (IAP) for Cloud Run service.
# Usage: ./deploy/setup_iap.sh <PROJECT_ID> [REGION]
#
# Grants access to @google.com and @cloudsufi.com domains.

PROJECT_ID="${1:?Usage: $0 <PROJECT_ID> [REGION]}"
REGION="${2:-us-central1}"
SERVICE="auto-schematization-agent"
IMAGE="us-central1-docker.pkg.dev/${PROJECT_ID}/auto-schematization-agent/app:latest"
BUCKET="${PROJECT_ID}-auto-schematization-agent-output"

echo "=== Setting up IAP for ${SERVICE} in ${PROJECT_ID} / ${REGION} ==="

# Step 1: Enable IAP API
echo "[1/5] Enabling IAP API..."
gcloud services enable iap.googleapis.com --project="${PROJECT_ID}"

# Step 2: Get project number and create IAP service agent
echo "[2/5] Setting up IAP service agent..."
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
IAP_SA="service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"

# Trigger IAP service agent creation by making an API call
gcloud beta services identity create \
  --service=iap.googleapis.com \
  --project="${PROJECT_ID}" 2>/dev/null || true

# Step 3: Grant IAP service agent permission to invoke Cloud Run
echo "[3/5] Granting IAP service agent run.invoker role..."
gcloud run services add-iam-policy-binding "${SERVICE}" \
  --region="${REGION}" \
  --member="serviceAccount:${IAP_SA}" \
  --role="roles/run.invoker" \
  --project="${PROJECT_ID}"

# Step 4: Redeploy with IAP enabled and authentication required
echo "[4/5] Redeploying with IAP enabled..."
gcloud beta run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --no-allow-unauthenticated \
  --iap \
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
  --add-volume-mount "volume=output-vol,mount-path=/app/ui_output" \
  --project="${PROJECT_ID}"

# Step 5: Grant IAP access to authorized domains
echo "[5/5] Granting IAP access to authorized domains..."

# Allow all @google.com users
gcloud iap web add-iam-policy-binding \
  --resource-type=cloud-run \
  --service="${SERVICE}" \
  --region="${REGION}" \
  --member="domain:google.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --project="${PROJECT_ID}"

# Allow all @cloudsufi.com users
gcloud iap web add-iam-policy-binding \
  --resource-type=cloud-run \
  --service="${SERVICE}" \
  --region="${REGION}" \
  --member="domain:cloudsufi.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --project="${PROJECT_ID}"

URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')
echo ""
echo "=== IAP Setup Complete ==="
echo "URL: ${URL}"
echo "Access: @google.com and @cloudsufi.com domains"
echo ""
echo "To add specific groups:"
echo "  gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=${SERVICE} --region=${REGION} --member='group:YOUR_GROUP@google.com' --role='roles/iap.httpsResourceAccessor' --project=${PROJECT_ID}"
