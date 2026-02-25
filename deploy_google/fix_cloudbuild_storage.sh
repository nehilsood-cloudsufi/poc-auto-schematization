#!/bin/bash
# ============================================================
# Fix: Cloud Build storage permission for deploy
# Run this if deploy fails with "storage.objects.get" 403 error
# Usage: ./deploy_google/fix_cloudbuild_storage.sh [PROJECT_ID]
# ============================================================

set -euo pipefail

PROJECT_ID="${1:-datcom-infosys-dev}"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
CLOUDBUILD_BUCKET="gs://${PROJECT_ID}_cloudbuild"

echo "=== Fixing Cloud Build Storage Permissions ==="
echo "  Project:            $PROJECT_ID"
echo "  Compute SA:         $COMPUTE_SA"
echo "  Cloud Build SA:     $CLOUDBUILD_SA"
echo "  Cloud Build Bucket: $CLOUDBUILD_BUCKET"
echo ""

# 1. Grant compute SA project-level storage access
echo ">>> 1/4 Granting compute SA project-level storage access..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/storage.objectAdmin" --quiet
echo "    Done."

# 2. Grant Cloud Build SA project-level storage access
echo ">>> 2/4 Granting Cloud Build SA project-level storage access..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/storage.objectAdmin" --quiet
echo "    Done."

# 3. Grant compute SA direct access on Cloud Build staging bucket
echo ">>> 3/4 Granting compute SA access on Cloud Build bucket..."
if gcloud storage buckets describe "$CLOUDBUILD_BUCKET" &>/dev/null; then
  gcloud storage buckets add-iam-policy-binding "$CLOUDBUILD_BUCKET" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/storage.objectAdmin" --quiet
  echo "    Done."
else
  echo "    Bucket $CLOUDBUILD_BUCKET not found (will be created on first build)."
  echo "    If deploy still fails, re-run this script after the first build attempt."
fi

# 4. Re-authenticate as current user (Cloud Shell may default to SA)
echo ">>> 4/4 Verifying user authentication..."
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null)
echo "    Active account: $ACTIVE_ACCOUNT"
if [[ "$ACTIVE_ACCOUNT" == *"compute@developer.gserviceaccount.com" ]]; then
  echo "    WARNING: Running as service account, not user account."
  echo "    Run: gcloud auth login --no-browser"
  echo "    Then retry deploy."
fi

echo ""
echo "=== Fix applied. Re-run: ./deploy_google/deploy_cloudtop.sh ==="
