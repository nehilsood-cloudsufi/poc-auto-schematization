#!/bin/bash
set -e

# Write storage_state.json from Secret Manager env var
if [ -n "$NOTEBOOKLM_STORAGE_STATE" ]; then
    echo "$NOTEBOOKLM_STORAGE_STATE" > /root/.notebooklm/storage_state.json
    # Also set the env var that notebooklm-py checks directly
    export NOTEBOOKLM_AUTH_JSON="$NOTEBOOKLM_STORAGE_STATE"
else
    echo "ERROR: NOTEBOOKLM_STORAGE_STATE not set"
    exit 1
fi

exec streamlit run viewer_app.py \
    --server.port=${PORT:-8080} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false \
    --server.fileWatcherType=none
