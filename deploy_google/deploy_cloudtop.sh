#!/bin/bash
set -euo pipefail

# ============================================================
# Agent B — Google Cloudtop / europe-west1 deployment
# Usage: ./deploy_google/deploy_cloudtop.sh [PROJECT_ID] [REGION]
# ============================================================

PROJECT_ID="${1:-datcom-infosys-dev}"
REGION="${2:-europe-west1}"
SERVICE="agent-b"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/agent-b/app:latest"
BUCKET="${PROJECT_ID}-agent-b-output"

echo "Deploying Agent B → ${PROJECT_ID} / ${REGION}"
echo "  Image:  ${IMAGE}"
echo "  Bucket: ${BUCKET}"

gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" --timeout=1200

gcloud run deploy "${SERVICE}" \
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

URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --format='value(status.url)')
echo "Deployed! URL: ${URL}"
