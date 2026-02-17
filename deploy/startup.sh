#!/bin/bash
set -e

echo '{"severity":"INFO","message":"Agent B container starting"}'

# Start DC MCP server in background
echo '{"severity":"INFO","message":"Starting MCP on port 3000"}'
datacommons-mcp serve http --port 3000 &

# Wait for MCP health (max 30s)
for i in $(seq 1 30); do
  if curl -sf http://localhost:3000/health > /dev/null 2>&1; then
    echo "{\"severity\":\"INFO\",\"message\":\"MCP ready\",\"seconds\":$i}"
    break
  fi
  [ $i -eq 30 ] && echo '{"severity":"WARNING","message":"MCP not ready after 30s"}'
  sleep 1
done

# Start Streamlit (exec → becomes PID 1, receives SIGTERM for graceful shutdown)
exec streamlit run src/ui/app.py \
  --server.port=${PORT:-8080} \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --server.enableCORS=false \
  --server.enableXsrfProtection=false \
  --browser.gatherUsageStats=false \
  --server.fileWatcherType=none
