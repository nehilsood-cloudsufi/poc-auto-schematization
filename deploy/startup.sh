#!/bin/bash
set -e

echo '{"severity":"INFO","message":"Agent B container starting"}'

# Start DC MCP server in background; capture PID so we can forward SIGTERM.
echo '{"severity":"INFO","message":"Starting MCP on port 3000"}'
datacommons-mcp serve http --port 3000 &
MCP_PID=$!

# On container stop, Cloud Run sends SIGTERM to PID 1 (uvicorn via exec).
# This trap only fires on signals received BEFORE the exec below. After exec,
# uvicorn owns signal handling; we forward via a parent wrapper only if needed.
trap 'kill -TERM "$MCP_PID" 2>/dev/null; wait "$MCP_PID" 2>/dev/null' SIGTERM SIGINT

# Wait for MCP health (max 30s)
mcp_ready=0
for i in $(seq 1 30); do
  if curl -sf http://localhost:3000/mcp/health > /dev/null 2>&1; then
    echo "{\"severity\":\"INFO\",\"message\":\"MCP ready\",\"seconds\":$i}"
    mcp_ready=1
    break
  fi
  sleep 1
done

if [ "$mcp_ready" = "0" ]; then
  echo '{"severity":"WARNING","message":"MCP not ready after 30s — serving API in degraded mode"}'
fi

# Start FastAPI. Use exec so uvicorn becomes PID 1 and receives SIGTERM directly.
# Note: after exec, the MCP child becomes orphaned but Cloud Run reaps the
# whole container on shutdown, so no leaked process persists across revisions.
exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level info
