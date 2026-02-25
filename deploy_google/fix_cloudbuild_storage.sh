#!/bin/bash
# ============================================================
# Fix: Cloud Build + Artifact Registry permissions for deploy
# Run this if deploy fails with storage or AR permission errors
# Usage: ./deploy_google/fix_cloudbuild_storage.sh [PROJECT_ID] [REGION]
# ============================================================

set -euo pipefail

PROJECT_ID="${1:-datcom-infosys-dev}"
REGION="${2:-europe-west1}"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
CLOUDBUILD_BUCKET="gs://${PROJECT_ID}_cloudbuild"
AR_REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/auto-schematization"

echo "=== Fixing Deploy Permissions ==="
echo "  Project:            $PROJECT_ID"
echo "  Region:             $REGION"
echo "  Compute SA:         $COMPUTE_SA"
echo "  Cloud Build SA:     $CLOUDBUILD_SA"
echo "  Cloud Build Bucket: $CLOUDBUILD_BUCKET"
echo "  Artifact Registry:  $AR_REPO"
echo ""

# 1. Grant compute SA project-level storage access
echo ">>> 1/6 Granting compute SA project-level storage access..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/storage.objectAdmin" --quiet
echo "    Done."

# 2. Grant Cloud Build SA project-level storage access
echo ">>> 2/6 Granting Cloud Build SA project-level storage access..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/storage.objectAdmin" --quiet
echo "    Done."

# 3. Grant compute SA direct access on Cloud Build staging bucket
echo ">>> 3/6 Granting compute SA access on Cloud Build bucket..."
if gcloud storage buckets describe "$CLOUDBUILD_BUCKET" &>/dev/null; then
  gcloud storage buckets add-iam-policy-binding "$CLOUDBUILD_BUCKET" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/storage.objectAdmin" --quiet
  echo "    Done."
else
  echo "    Bucket $CLOUDBUILD_BUCKET not found yet — skipping (created on first build)."
fi

# 4. Grant Cloud Build SA Artifact Registry write access (for docker push)
echo ">>> 4/6 Granting Cloud Build SA Artifact Registry writer..."
gcloud artifacts repositories add-iam-policy-binding auto-schematization \
  --location="$REGION" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/artifactregistry.writer" --quiet
echo "    Done."

# 5. Grant compute SA Artifact Registry write access
echo ">>> 5/6 Granting compute SA Artifact Registry writer..."
gcloud artifacts repositories add-iam-policy-binding auto-schematization \
  --location="$REGION" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/artifactregistry.writer" --quiet
echo "    Done."

# 6. Check active authentication
echo ">>> 6/6 Verifying user authentication..."
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null)
echo "    Active account: $ACTIVE_ACCOUNT"
if [[ "$ACTIVE_ACCOUNT" == *"compute@developer.gserviceaccount.com" ]]; then
  echo "    WARNING: Running as service account, not user account."
  echo "    Run: gcloud auth login --no-browser"
  echo "    Then retry deploy."
fi

echo ""
echo "=== All permissions fixed. Re-run: ./deploy_google/deploy_cloudtop.sh ==="
