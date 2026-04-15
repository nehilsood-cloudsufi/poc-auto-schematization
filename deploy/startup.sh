#!/bin/bash
set -e

echo '{"severity":"INFO","message":"Agent B container starting"}'

# Start DC MCP server in background
echo '{"severity":"INFO","message":"Starting MCP on port 3000"}'
datacommons-mcp serve http --port 3000 &

# Wait for MCP health (max 30s)
for i in $(seq 1 30); do
  if curl -sf http://localhost:3000/mcp/health > /dev/null 2>&1; then
    echo "{\"severity\":\"INFO\",\"message\":\"MCP ready\",\"seconds\":$i}"
    break
  fi
  [ $i -eq 30 ] && echo '{"severity":"WARNING","message":"MCP not ready after 30s"}'
  sleep 1
done

# Start FastAPI (exec → becomes PID 1, receives SIGTERM for graceful shutdown)
exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level info
