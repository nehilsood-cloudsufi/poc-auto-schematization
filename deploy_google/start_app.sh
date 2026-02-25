#!/bin/bash
# ============================================================
# Auto-Schematization — Start & Access the deployed app
# Usage: ./deploy_google/start_app.sh [PROJECT_ID] [REGION] [PORT]
# ============================================================

set -euo pipefail

PROJECT_ID="${1:-datcom-infosys-dev}"
REGION="${2:-europe-west1}"
PORT="${3:-8080}"
SERVICE="auto-schematization"

echo "============================================"
echo "  Auto-Schematization — App Access"
echo "============================================"
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "  Service: $SERVICE"
echo ""

# --- Step 1: Verify gcloud auth ---
echo ">>> Checking authentication..."
if ! gcloud auth print-identity-token &>/dev/null; then
  echo ""
  echo "ERROR: Not authenticated. Run:"
  echo "  gcloud auth login"
  exit 1
fi
ACCOUNT=$(gcloud config get-value account 2>/dev/null)
echo "    Authenticated as: $ACCOUNT"
echo ""

# --- Step 2: Verify service exists ---
echo ">>> Checking Cloud Run service..."
URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --project="$PROJECT_ID" --format='value(status.url)' 2>/dev/null || true)
if [ -z "$URL" ]; then
  echo ""
  echo "ERROR: Service '$SERVICE' not found in $REGION."
  echo "  Deploy first: ./deploy_google/setup_and_deploy.sh"
  exit 1
fi
echo "    Service URL: $URL"
echo ""

# --- Step 3: Quick health check ---
echo ">>> Health check (authenticated curl)..."
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${URL}/_stcore/health" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
  echo "    Health: OK (200)"
else
  echo "    Health: $HTTP_CODE (may still be starting up — proceeding)"
fi
echo ""

# --- Step 4: Start proxy ---
echo "============================================"
echo "  Starting Cloud Run Proxy on port $PORT"
echo "============================================"
echo ""
echo "  The proxy injects your Google identity token into all requests."
echo ""
echo "  === How to open the app ==="
echo ""
echo "  Cloud Shell:"
echo "    Click Web Preview (top-right) → 'Preview on port $PORT'"
echo ""
echo "  Cloudtop / local machine:"
echo "    Open http://localhost:$PORT in your browser"
echo ""
echo "  Press Ctrl+C to stop the proxy."
echo ""
echo "--------------------------------------------"

exec gcloud run services proxy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --port="$PORT"
