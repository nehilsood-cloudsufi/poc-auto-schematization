#!/bin/bash
# ============================================================
# Auto-Schematization — Full Setup & Deploy (one script)
# Runs: permission check → infra setup → build → deploy → IAP
# For code-only redeployment, use deploy_cloudtop.sh instead.
# See DEPLOYMENT.md for the full guide.
# Usage: ./deploy_google/setup_and_deploy.sh [PROJECT_ID] [REGION]
# ============================================================

set -euo pipefail

CURRENT_STEP=""
on_error() {
  local exit_code=$?
  echo ""
  echo "============================================"
  echo "  SETUP FAILED at: ${CURRENT_STEP:-unknown step} (exit code $exit_code)"
  echo "============================================"
  echo ""
  echo "  Quick fixes by step:"
  echo "    Step 1 (Permissions)  → Ask manager for missing roles"
  echo "    Step 2 (APIs)         → Run: gcloud services enable run.googleapis.com --quiet"
  echo "    Step 3 (Infra)        → Re-run this script (idempotent)"
  echo "    Step 4 (Build perms)  → Re-run this script (idempotent)"
  echo "    Step 5 (Build)        → Check .gcloudignore, then re-run"
  echo "    Step 6 (Deploy)       → Run ./deploy_google/diagnose.sh"
  echo "    Step 7-8 (Access/IAP) → Run ./deploy_google/setup_iap.sh"
  echo ""
  echo "  See DEPLOYMENT.md Section 10 for detailed troubleshooting."
}
trap on_error ERR

PROJECT_ID="${1:-datcom-infosys-dev}"
REGION="${2:-europe-west1}"
SERVICE="auto-schematization"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/agent-b/app:latest"
BUCKET="${PROJECT_ID}-agent-b-output"

echo "============================================"
echo "  Auto-Schematization — Full Setup & Deploy"
echo "============================================"
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "  Service: $SERVICE"
echo ""

gcloud config set project "$PROJECT_ID" --quiet 2>/dev/null

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
CLOUDBUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

# ==========================================================
# STEP 1: Permission Check
# ==========================================================
CURRENT_STEP="Step 1/8: Permission check"
echo ">>> Step 1/8: Permission check..."
echo ""

PASSED=0
FAILED=0
FAILED_ROLES=()

check() {
  local num="$1" label="$2" role="$3"; shift 3
  echo -n "    $num. $label: "
  if "$@" &>/dev/null; then
    echo "PASS"
    ((PASSED++)) || true
  else
    echo "FAIL — need $role"
    ((FAILED++)) || true
    FAILED_ROLES+=("$role")
  fi
}

check 1 "Project access"    "project viewer"                       gcloud projects describe "$PROJECT_ID" --format="value(projectId)"
check 2 "Enable APIs"       "roles/serviceusage.serviceUsageAdmin" gcloud services list --enabled --limit=1
check 3 "Cloud Run"         "roles/run.admin"                      gcloud run services list --region="$REGION"
check 4 "Cloud Build"       "roles/cloudbuild.builds.editor"       gcloud builds list --limit=1
check 5 "Artifact Registry" "roles/artifactregistry.admin"         gcloud artifacts repositories list --location="$REGION"
check 6 "Secret Manager"    "roles/secretmanager.admin"            gcloud secrets list
check 7 "GCS Storage"       "roles/storage.admin"                  gcloud storage buckets list --limit=1
check 8 "Service Accounts"  "roles/iam.serviceAccountUser"         gcloud iam service-accounts list
check 9 "Logging"           "roles/logging.viewer"                 gcloud logging read "" --limit=1 --freshness=1d

echo ""
if [ "$FAILED" -gt 0 ]; then
  echo "SETUP STOPPED: $FAILED permission(s) missing."
  echo ""
  echo "Ask your manager to grant:"
  for role in "${FAILED_ROLES[@]}"; do
    echo "  - $role"
  done
  exit 1
fi
echo "    All 9 checks passed."
echo ""

# ==========================================================
# STEP 2: Enable APIs
# ==========================================================
CURRENT_STEP="Step 2/8: Enable APIs"
echo ">>> Step 2/8: Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  iap.googleapis.com \
  --quiet
echo "    Done."
echo ""

# ==========================================================
# STEP 3: Create Infrastructure (idempotent)
# ==========================================================
CURRENT_STEP="Step 3/8: Create infrastructure"
echo ">>> Step 3/8: Creating infrastructure..."

# Artifact Registry
echo -n "    Artifact Registry: "
if gcloud artifacts repositories describe agent-b --location="$REGION" &>/dev/null; then
  echo "exists"
else
  gcloud artifacts repositories create agent-b \
    --repository-format=docker \
    --location="$REGION" \
    --description="Auto-Schematization container images" --quiet
  echo "created"
fi

# Secrets
create_secret() {
  local name="$1" prompt="$2"
  if gcloud secrets describe "$name" &>/dev/null; then
    echo "    Secret '$name': exists"
    return
  fi
  read -rp "    Enter $prompt: " value
  if [ -z "$value" ]; then
    echo "    Secret '$name': skipped (empty)"
    return
  fi
  echo -n "$value" | gcloud secrets create "$name" --data-file=-
  gcloud secrets add-iam-policy-binding "$name" \
    --member="serviceAccount:${COMPUTE_SA}" --role="roles/secretmanager.secretAccessor" --quiet >/dev/null
  echo "    Secret '$name': created"
}

create_secret "GOOGLE_API_KEY" "Gemini API key (from https://aistudio.google.com/apikey)"
create_secret "DC_API_KEY" "Data Commons API key (from https://apikeys.datacommons.org)"
create_secret "GOOGLE_SHEET_ID" "Google Sheet ID (optional, press Enter to skip)"

# GCS Bucket
echo -n "    GCS Bucket: "
if gcloud storage buckets describe "gs://${BUCKET}" &>/dev/null; then
  echo "exists"
else
  gcloud storage buckets create "gs://${BUCKET}" \
    --location="$REGION" \
    --uniform-bucket-level-access --quiet
  echo "created"
fi
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${COMPUTE_SA}" --role="roles/storage.objectAdmin" --quiet >/dev/null

echo ""

# ==========================================================
# STEP 4: Fix Build Permissions
# ==========================================================
CURRENT_STEP="Step 4/8: Fix build permissions"
echo ">>> Step 4/8: Fixing build permissions..."

# Storage access for source upload
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/storage.objectAdmin" --quiet >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/storage.objectAdmin" --quiet >/dev/null

# Cloud Build bucket access
CLOUDBUILD_BUCKET="gs://${PROJECT_ID}_cloudbuild"
if gcloud storage buckets describe "$CLOUDBUILD_BUCKET" &>/dev/null; then
  gcloud storage buckets add-iam-policy-binding "$CLOUDBUILD_BUCKET" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/storage.objectAdmin" --quiet >/dev/null
fi

# Artifact Registry write access
gcloud artifacts repositories add-iam-policy-binding agent-b \
  --location="$REGION" \
  --member="serviceAccount:${CLOUDBUILD_SA}" \
  --role="roles/artifactregistry.writer" --quiet >/dev/null 2>&1 || true
gcloud artifacts repositories add-iam-policy-binding agent-b \
  --location="$REGION" \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/artifactregistry.writer" --quiet >/dev/null 2>&1 || true

echo "    Done."
echo ""

# ==========================================================
# STEP 5: Build & Push Image
# ==========================================================
CURRENT_STEP="Step 5/8: Build & push image"
echo ">>> Step 5/8: Building and pushing image via Cloud Build..."
echo "    (First build: ~5-8 min. Subsequent: ~2-3 min)"
echo ""

BUILD_OUTPUT=$(mktemp)
if ! gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" --timeout=1200 2>&1 | tee "$BUILD_OUTPUT"; then
  echo ""
  echo "BUILD FAILED."
  if grep -q "storage.objects.get" "$BUILD_OUTPUT"; then
    echo "CAUSE: Storage permission issue."
  elif grep -q "artifactregistry.repositories.uploadArtifacts" "$BUILD_OUTPUT"; then
    echo "CAUSE: Artifact Registry permission issue."
  elif grep -q "TIMEOUT" "$BUILD_OUTPUT"; then
    echo "CAUSE: Build timed out."
  else
    echo "CAUSE: Check build logs: gcloud builds log \$(gcloud builds list --limit=1 --format='value(id)')"
  fi
  rm -f "$BUILD_OUTPUT"
  exit 1
fi
rm -f "$BUILD_OUTPUT"
echo ""

# ==========================================================
# STEP 6: Deploy to Cloud Run
# ==========================================================
CURRENT_STEP="Step 6/8: Deploy to Cloud Run"
echo ">>> Step 6/8: Deploying to Cloud Run..."
echo ""

DEPLOY_OUTPUT=$(mktemp)
if ! gcloud beta run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --no-allow-unauthenticated \
  --iap \
  --ingress=all \
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
  echo "DEPLOY FAILED."
  if grep -q "secretmanager" "$DEPLOY_OUTPUT" || grep -q "Secret" "$DEPLOY_OUTPUT"; then
    echo "CAUSE: Secret Manager binding issue."
  elif grep -q "iam.serviceAccounts.actAs" "$DEPLOY_OUTPUT"; then
    echo "CAUSE: Missing roles/iam.serviceAccountUser."
  else
    echo "CAUSE: Check logs: gcloud logging read 'resource.type=\"cloud_run_revision\" AND severity>=ERROR' --project=${PROJECT_ID} --limit=20"
  fi
  rm -f "$DEPLOY_OUTPUT"
  exit 1
fi
rm -f "$DEPLOY_OUTPUT"
echo ""

# ==========================================================
# STEP 7: Grant Access & Configure IAP
# ==========================================================
CURRENT_STEP="Step 7/8: Grant access"
echo ">>> Step 7/8: Granting Cloud Run invoker access..."

gcloud run services add-iam-policy-binding "${SERVICE}" \
  --region="${REGION}" --member="domain:google.com" \
  --role="roles/run.invoker" --quiet >/dev/null 2>&1 || true
gcloud run services add-iam-policy-binding "${SERVICE}" \
  --region="${REGION}" --member="group:datcom-cloudsufi@google.com" \
  --role="roles/run.invoker" --quiet >/dev/null 2>&1 || true
gcloud run services add-iam-policy-binding "${SERVICE}" \
  --region="${REGION}" --member="group:datcom-core@google.com" \
  --role="roles/run.invoker" --quiet >/dev/null 2>&1 || true
echo "    Done."
echo ""

# ==========================================================
# STEP 8: Configure IAP for browser access
# ==========================================================
CURRENT_STEP="Step 8/8: Configure IAP"
echo ">>> Step 8/8: Configuring IAP for browser access..."

# Enable IAP API
gcloud services enable iap.googleapis.com --quiet 2>/dev/null || true

# Create IAP service agent
gcloud beta services identity create --service=iap.googleapis.com --project="$PROJECT_ID" 2>/dev/null || true

# Grant IAP service agent Cloud Run invoker
IAP_SA="service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${IAP_SA}" \
  --role="roles/run.invoker" \
  --quiet >/dev/null 2>&1 || true

# Grant IAP web access to authorized groups
gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run --service="$SERVICE" --region="$REGION" \
  --member="domain:google.com" --role="roles/iap.httpsResourceAccessor" \
  --condition=None --quiet 2>/dev/null || true
gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run --service="$SERVICE" --region="$REGION" \
  --member="group:datcom-cloudsufi@google.com" --role="roles/iap.httpsResourceAccessor" \
  --condition=None --quiet 2>/dev/null || true
gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run --service="$SERVICE" --region="$REGION" \
  --member="group:datcom-core@google.com" --role="roles/iap.httpsResourceAccessor" \
  --condition=None --quiet 2>/dev/null || true

echo "    Done."

URL=$(gcloud run services describe "${SERVICE}" --region="${REGION}" --format='value(status.url)')

echo ""
echo "============================================"
echo "  SETUP & DEPLOY COMPLETE"
echo "============================================"
echo ""
echo "  Service: $SERVICE"
echo "  URL:     $URL"
echo "  Bucket:  gs://${BUCKET}"
echo ""
echo "  === How to Access the App ==="
echo ""
echo "  Open the URL above directly in your browser."
echo "  Google will prompt for login, then show the Streamlit app."
echo ""
echo "  === Share with Others ==="
echo ""
echo "  Anyone with @google.com account can open the URL directly."
echo "  No proxy, Cloud Shell, or setup needed."
echo ""
echo "  === Troubleshooting ==="
echo ""
echo "  If you see 403, run: ./deploy_google/setup_iap.sh"
echo "  IAP propagation may take 1-2 minutes."
echo ""
