#!/bin/bash
set -euo pipefail

# ============================================================
# Auto-Schematization — Google Cloudtop / europe-west1 deployment
# Usage: ./deploy_google/deploy_cloudtop.sh [PROJECT_ID] [REGION]
# ============================================================

PROJECT_ID="${1:-datcom-infosys-dev}"
REGION="${2:-europe-west1}"
SERVICE="auto-schematization"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/agent-b/app:latest"
BUCKET="${PROJECT_ID}-agent-b-output"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null || true)
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

echo "============================================"
echo "  Auto-Schematization Deploy → ${PROJECT_ID} / ${REGION}"
echo "============================================"
echo "  Image:          ${IMAGE}"
echo "  Bucket:         ${BUCKET}"
echo "  Cloud Build SA: ${CLOUDBUILD_SA}"
echo ""

# --- Step 1: Pre-flight checks ---
echo ">>> Step 1/3: Pre-flight checks..."

# Check Artifact Registry repo exists
if ! gcloud artifacts repositories describe agent-b --location="$REGION" &>/dev/null; then
  echo ""
  echo "DEPLOY FAILED: Artifact Registry repo 'agent-b' not found in ${REGION}."
  echo ""
  echo "FIX: Run ./deploy_google/infra_setup.sh first to create infrastructure."
  exit 1
fi
echo "    Artifact Registry: OK"

# Check secrets exist
MISSING_SECRETS=()
for secret in GOOGLE_API_KEY DC_API_KEY; do
  if ! gcloud secrets describe "$secret" &>/dev/null; then
    MISSING_SECRETS+=("$secret")
  fi
done
if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
  echo ""
  echo "DEPLOY FAILED: Required secrets missing: ${MISSING_SECRETS[*]}"
  echo ""
  echo "FIX: Run ./deploy_google/infra_setup.sh to create secrets."
  exit 1
fi
echo "    Secrets: OK"

# Check GCS bucket exists
if ! gcloud storage buckets describe "gs://${BUCKET}" &>/dev/null; then
  echo ""
  echo "DEPLOY FAILED: GCS bucket gs://${BUCKET} not found."
  echo ""
  echo "FIX: Run ./deploy_google/infra_setup.sh to create the bucket."
  exit 1
fi
echo "    GCS Bucket: OK"
echo ""

# --- Step 2: Build and push image ---
echo ">>> Step 2/3: Building and pushing image via Cloud Build..."
echo "    (This may take 5-8 min on first build, 2-3 min on subsequent builds)"
echo ""

BUILD_OUTPUT=$(mktemp)
if ! gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" --timeout=1200 2>&1 | tee "$BUILD_OUTPUT"; then
  echo ""
  echo "============================================"
  echo "  DEPLOY FAILED: Cloud Build error"
  echo "============================================"
  echo ""

  if grep -q "storage.objects.get" "$BUILD_OUTPUT"; then
    echo "CAUSE: Cloud Build SA lacks storage access for source upload."
    echo ""
    echo "FIX: Run ./deploy_google/fix_cloudbuild_storage.sh"
  elif grep -q "artifactregistry.repositories.uploadArtifacts" "$BUILD_OUTPUT"; then
    echo "CAUSE: Cloud Build SA lacks permission to push to Artifact Registry."
    echo ""
    echo "FIX: Run ./deploy_google/fix_cloudbuild_storage.sh"
  elif grep -q "TIMEOUT" "$BUILD_OUTPUT"; then
    echo "CAUSE: Build timed out (>20 min)."
    echo ""
    echo "FIX: Check .gcloudignore is present and not uploading unnecessary files."
    echo "     Then retry: ./deploy_google/deploy_cloudtop.sh"
  elif grep -q "PERMISSION_DENIED" "$BUILD_OUTPUT"; then
    echo "CAUSE: Missing IAM permissions."
    echo ""
    echo "FIX: Run ./deploy_google/permission_check.sh to identify missing roles."
  else
    echo "CAUSE: Unknown build failure."
    echo ""
    echo "DEBUG: Check build logs:"
    echo "  gcloud builds log \$(gcloud builds list --limit=1 --format='value(id)')"
  fi

  rm -f "$BUILD_OUTPUT"
  exit 1
fi
rm -f "$BUILD_OUTPUT"
echo ""

# --- Step 3: Deploy to Cloud Run ---
echo ">>> Step 3/3: Deploying to Cloud Run..."
echo ""

DEPLOY_OUTPUT=$(mktemp)
if ! gcloud run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --no-allow-unauthenticated \
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
  --add-volume-mount "volume=output-vol,mount-path=/app/ui_output" 2>&1 | tee "$DEPLOY_OUTPUT"; then

  echo ""
  echo "============================================"
  echo "  DEPLOY FAILED: Cloud Run error"
  echo "============================================"
  echo ""

  if grep -q "secretmanager" "$DEPLOY_OUTPUT" || grep -q "Secret" "$DEPLOY_OUTPUT"; then
    echo "CAUSE: Secret Manager binding issue."
    echo ""
    echo "FIX: Ensure the compute SA has secretAccessor on each secret:"
    echo "  gcloud secrets add-iam-policy-binding GOOGLE_API_KEY \\"
    echo "    --member=\"serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com\" \\"
    echo "    --role=\"roles/secretmanager.secretAccessor\""
  elif grep -q "iam.serviceAccounts.actAs" "$DEPLOY_OUTPUT"; then
    echo "CAUSE: Missing roles/iam.serviceAccountUser."
    echo ""
    echo "FIX: Ask your manager to grant roles/iam.serviceAccountUser on the project."
  elif grep -q "PERMISSION_DENIED" "$DEPLOY_OUTPUT"; then
    echo "CAUSE: Missing IAM permissions for Cloud Run."
    echo ""
    echo "FIX: Run ./deploy_google/permission_check.sh to identify missing roles."
  else
    echo "CAUSE: Unknown deploy failure."
    echo ""
    echo "DEBUG: Check logs:"
    echo "  gcloud logging read 'resource.type=\"cloud_run_revision\" AND severity>=ERROR' \\"
    echo "    --project=${PROJECT_ID} --limit=20"
  fi

  rm -f "$DEPLOY_OUTPUT"
  exit 1
fi
rm -f "$DEPLOY_OUTPUT"

# --- Grant domain-level access (google.com users) ---
echo ">>> Granting access to google.com domain..."
gcloud run services add-iam-policy-binding "${SERVICE}" \
  --region="${REGION}" \
  --member="domain:google.com" \
  --role="roles/run.invoker" --quiet 2>/dev/null || true
echo "    Done."

# --- Success ---
URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --format='value(status.url)')
echo ""
echo "============================================"
echo "  DEPLOY SUCCESS"
echo "============================================"
echo "  URL:    ${URL}"
echo "  Bucket: gs://${BUCKET}"
echo ""
echo "  Access:       All @google.com users (sign in with corporate account)"
echo "  Health check: curl -H \"Authorization: Bearer \$(gcloud auth print-identity-token)\" ${URL}/_stcore/health"
echo "  Logs:         gcloud logging read 'resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"auto-schematization\"' --project=${PROJECT_ID} --limit=20"
