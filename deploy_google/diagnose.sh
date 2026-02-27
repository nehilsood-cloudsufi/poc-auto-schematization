#!/bin/bash
# ============================================================
# Diagnose: Check Cloud Run service health, status, and logs
# Usage: ./deploy_google/diagnose.sh [PROJECT_ID] [REGION]
# ============================================================

set -euo pipefail

PROJECT_ID="${1:-datcom-infosys-dev}"
REGION="${2:-europe-west1}"
SERVICE="auto-schematization"

URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)' 2>/dev/null || true)

echo "=== Diagnosing $SERVICE ==="
echo "  Project: $PROJECT_ID"
echo "  Region:  $REGION"
echo "  URL:     $URL"
echo ""

# 1. Authenticated health check
echo ">>> 1/4 Health check (authenticated)..."
TOKEN=$(gcloud auth print-identity-token 2>/dev/null || true)
if [ -n "$TOKEN" ] && [ -n "$URL" ]; then
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "${URL}/_stcore/health" 2>/dev/null || echo "000")
  echo "    HTTP status: $HTTP_CODE"
  if [ "$HTTP_CODE" = "200" ]; then
    BODY=$(curl -s -H "Authorization: Bearer $TOKEN" "${URL}/_stcore/health" 2>/dev/null)
    echo "    Response: $BODY"
  elif [ "$HTTP_CODE" = "403" ]; then
    echo "    Still Forbidden — IAM binding not effective yet or account mismatch."
  elif [ "$HTTP_CODE" = "000" ]; then
    echo "    Could not connect — service may not be running."
  else
    echo "    Unexpected status — check logs below."
  fi
else
  echo "    Could not get identity token or URL."
fi
echo ""

# 2. Revision status
echo ">>> 2/4 Revision status..."
gcloud run revisions list --service="$SERVICE" --region="$REGION" --format="table(REVISION,ACTIVE,SERVICE,DEPLOYED)" 2>&1
echo ""

# 3. IAM policy
echo ">>> 3/4 Current IAM policy..."
gcloud run services get-iam-policy "$SERVICE" --region="$REGION" 2>&1
echo ""

# 4. Recent logs
echo ">>> 4/4 Recent logs (last 30 entries, warnings+errors)..."
gcloud logging read \
  "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"$SERVICE\" AND severity>=WARNING" \
  --project="$PROJECT_ID" --limit=30 \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" 2>&1
echo ""

echo "=== Diagnosis complete. Paste this output to get help. ==="
echo ""
echo "=== Common Fixes ==="
echo "  403 Forbidden?       → ./deploy_google/setup_iap.sh"
echo "  Container crashing?  → Check logs above for ModuleNotFoundError or missing secrets"
echo "  No revisions?        → ./deploy_google/deploy_cloudtop.sh"
echo "  Permission denied?   → ./deploy_google/permission_check.sh"
echo "  See DEPLOYMENT.md Section 10 for detailed troubleshooting."
