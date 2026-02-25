#!/bin/bash
# ============================================================
# Permission Self-Check for datcom-infosys-dev
# Run AFTER your manager grants IAM roles
# Usage: ./deploy_google/permission_check.sh [PROJECT_ID]
# ============================================================

PROJECT_ID="${1:-datcom-infosys-dev}"
REGION="europe-west1"

PASSED=0
FAILED=0
FAILED_ROLES=()

check() {
  local num="$1"
  local label="$2"
  local role="$3"
  shift 3

  echo -n "$num. $label: "
  if "$@" &>/dev/null; then
    echo "PASS"
    ((PASSED++))
  else
    echo "FAIL — need $role"
    ((FAILED++))
    FAILED_ROLES+=("$num. $label → $role")
  fi
}

gcloud config set project "$PROJECT_ID" --quiet 2>/dev/null

echo "=== Permission Self-Check for $PROJECT_ID ==="
echo ""

check 1 "Project access"      "project viewer"                       gcloud projects describe "$PROJECT_ID" --format="value(projectId)"
check 2 "Enable APIs"         "roles/serviceusage.serviceUsageAdmin" gcloud services list --enabled --limit=1
check 3 "Cloud Run"           "roles/run.admin"                      gcloud run services list --region="$REGION"
check 4 "Cloud Build"         "roles/cloudbuild.builds.editor"       gcloud builds list --limit=1
check 5 "Artifact Registry"   "roles/artifactregistry.admin"         gcloud artifacts repositories list --location="$REGION"
check 6 "Secret Manager"      "roles/secretmanager.admin"            gcloud secrets list
check 7 "GCS Storage"         "roles/storage.admin"                  gcloud storage buckets list --limit=1
check 8 "Service Accounts"    "roles/iam.serviceAccountUser"         gcloud iam service-accounts list
check 9 "Logging"             "roles/logging.viewer"                 gcloud logging read "" --limit=1 --freshness=1d

echo ""
echo "==========================================="
echo "  SUMMARY: $PASSED passed, $FAILED failed"
echo "==========================================="

if [ "$FAILED" -eq 0 ]; then
  echo ""
  echo "All checks passed! You're ready to deploy."
else
  echo ""
  echo "Missing roles — ask your manager to grant:"
  echo ""
  for item in "${FAILED_ROLES[@]}"; do
    echo "  $item"
  done
  echo ""
  echo "Send this to your manager:"
  echo "  \"Could you grant me the following roles on project $PROJECT_ID:\""
  for item in "${FAILED_ROLES[@]}"; do
    role="${item##*→ }"
    echo "    - $role"
  done
fi
