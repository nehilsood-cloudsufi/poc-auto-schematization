#!/bin/bash
# ============================================================
# Auto-Schematization — Enable IAP on Cloud Run
# Enables Identity-Aware Proxy so the app is accessible
# directly via browser with Google login (no proxy needed).
#
# Usage: ./deploy_google/setup_iap.sh [PROJECT_ID] [REGION]
# ============================================================

set -euo pipefail

on_error() {
  local exit_code=$?
  echo ""
  echo "============================================"
  echo "  IAP SETUP FAILED (exit code $exit_code)"
  echo "============================================"
  echo ""
  echo "  Quick fixes:"
  echo "  1. Service not found?  → Run ./deploy_google/setup_and_deploy.sh first"
  echo "  2. PERMISSION_DENIED?  → Run ./deploy_google/permission_check.sh"
  echo "  3. beta not installed? → gcloud components install beta"
  echo "  4. Still stuck?        → Run ./deploy_google/diagnose.sh and share output"
  echo ""
  echo "  See DEPLOYMENT.md Section 10 for more troubleshooting."
}
trap on_error ERR

PROJECT_ID="${1:-datcom-infosys-dev}"
REGION="${2:-europe-west1}"
SERVICE="auto-schematization"

echo "============================================"
echo "  Enable IAP for Cloud Run"
echo "============================================"
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "  Service: $SERVICE"
echo ""

gcloud config set project "$PROJECT_ID" --quiet 2>/dev/null

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')

# --- Step 1: Enable IAP API ---
echo ">>> Step 1/5: Enabling IAP API..."
gcloud services enable iap.googleapis.com --quiet
echo "    Done."
echo ""

# --- Step 2: Create IAP service agent ---
echo ">>> Step 2/5: Creating IAP service agent..."
gcloud beta services identity create \
  --service=iap.googleapis.com \
  --project="$PROJECT_ID" 2>/dev/null || true
echo "    Done."
echo ""

# --- Step 3: Grant IAP service agent Cloud Run Invoker role ---
echo ">>> Step 3/5: Granting IAP service agent Cloud Run Invoker role..."
IAP_SA="service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${IAP_SA}" \
  --role="roles/run.invoker" \
  --quiet >/dev/null 2>&1 || true
echo "    Granted roles/run.invoker to ${IAP_SA}"
echo ""

# --- Step 4: Enable IAP on the Cloud Run service ---
echo ">>> Step 4/5: Enabling IAP on Cloud Run service..."
echo "    (Redeploying with --iap flag...)"
echo ""

# Get the current image
CURRENT_IMAGE=$(gcloud run services describe "$SERVICE" \
  --region="$REGION" \
  --format='value(spec.template.spec.containers[0].image)' 2>/dev/null)

if [ -z "$CURRENT_IMAGE" ]; then
  echo "ERROR: Could not get current image for service '$SERVICE'."
  echo "  Deploy the service first: ./deploy_google/deploy_cloudtop.sh"
  exit 1
fi

echo "    Current image: $CURRENT_IMAGE"

# Redeploy with --iap flag using gcloud beta
gcloud beta run deploy "$SERVICE" \
  --image "$CURRENT_IMAGE" \
  --region "$REGION" \
  --no-allow-unauthenticated \
  --iap \
  --quiet

echo ""
echo "    IAP enabled."
echo ""

# --- Step 5: Grant access ---
echo ">>> Step 5/5: Granting IAP access to google.com domain..."

gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run \
  --service="$SERVICE" \
  --region="$REGION" \
  --member="domain:google.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --condition=None \
  --quiet 2>/dev/null || true

gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run \
  --service="$SERVICE" \
  --region="$REGION" \
  --member="group:datcom-cloudsufi@google.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --condition=None \
  --quiet 2>/dev/null || true

gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run \
  --service="$SERVICE" \
  --region="$REGION" \
  --member="group:datcom-core@google.com" \
  --role="roles/iap.httpsResourceAccessor" \
  --condition=None \
  --quiet 2>/dev/null || true

echo "    Done."

# --- Success ---
URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')

echo ""
echo "============================================"
echo "  IAP ENABLED SUCCESSFULLY"
echo "============================================"
echo ""
echo "  URL: $URL"
echo ""
echo "  Anyone with @google.com / datcom-cloudsufi / datcom-core access"
echo "  can now open the URL directly in their browser."
echo ""
echo "  On first visit, Google will prompt for login, then redirect"
echo "  to the Streamlit app. No proxy or Cloud Shell needed."
echo ""
echo "  NOTE: IAP propagation may take 1-2 minutes."
echo "  If you still see 403, wait and refresh."
echo ""
