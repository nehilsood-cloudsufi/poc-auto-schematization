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

echo "=== Fixing Cloud Build Storage Permissions ==="
echo "  Project:          $PROJECT_ID"
echo "  Compute SA:       $COMPUTE_SA"
echo "  Cloud Build SA:   $CLOUDBUILD_SA"
echo ""

# 1. Grant compute SA project-level storage access (for source upload)
echo ">>> Granting compute SA project-level storage access..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/storage.objectAdmin" --quiet
echo "    Done."

# 2. Grant Cloud Build SA storage access
echo ">>> Granting Cloud Build SA storage access..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/storage.objectAdmin" --quiet
echo "    Done."

echo ""
echo "=== Fix applied. Re-run: ./deploy_google/deploy_cloudtop.sh ==="
