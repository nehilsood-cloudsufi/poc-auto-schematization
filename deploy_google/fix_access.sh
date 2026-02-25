#!/bin/bash
# ============================================================
# Fix: Grant Cloud Run invoker access for auto-schematization
# Run this if you get "Forbidden" when accessing the app URL
# Usage: ./deploy_google/fix_access.sh [PROJECT_ID] [REGION]
# ============================================================

set -euo pipefail

PROJECT_ID="${1:-datcom-infosys-dev}"
REGION="${2:-europe-west1}"
SERVICE="auto-schematization"

CURRENT_USER=$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null)

echo "=== Fixing Cloud Run Access ==="
echo "  Service: $SERVICE"
echo "  Region:  $REGION"
echo "  Your account: $CURRENT_USER"
echo ""

# 1. Grant your own account
echo ">>> 1/4 Granting invoker access to $CURRENT_USER..."
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="user:${CURRENT_USER}" \
  --role="roles/run.invoker" --quiet 2>&1 && echo "    Done." || echo "    FAILED (may need roles/run.admin)"

# 2. Grant datcom-cloudsufi group
echo ">>> 2/4 Granting invoker access to datcom-cloudsufi@google.com..."
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="group:datcom-cloudsufi@google.com" \
  --role="roles/run.invoker" --quiet 2>&1 && echo "    Done." || echo "    FAILED"

# 3. Grant datcom-core group
echo ">>> 3/4 Granting invoker access to datcom-core@google.com..."
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="group:datcom-core@google.com" \
  --role="roles/run.invoker" --quiet 2>&1 && echo "    Done." || echo "    FAILED"

# 4. Try domain:google.com (may be blocked by org policy)
echo ">>> 4/4 Granting invoker access to domain:google.com..."
gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="domain:google.com" \
  --role="roles/run.invoker" --quiet 2>&1 && echo "    Done." || echo "    FAILED (org policy may block this — that's OK)"

# Verify current IAM policy
echo ""
echo "=== Current IAM Policy ==="
gcloud run services get-iam-policy "$SERVICE" --region="$REGION" 2>&1

# Show URL
URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)' 2>/dev/null)
echo ""
echo "=== Access Fix Complete ==="
echo "  URL: $URL"
echo ""
echo "  Open in Chrome (signed in with your @google.com account)."
echo "  If still Forbidden, ask your manager to run:"
echo "    gcloud run services add-iam-policy-binding $SERVICE \\"
echo "      --region=$REGION --member=user:${CURRENT_USER} --role=roles/run.invoker"
