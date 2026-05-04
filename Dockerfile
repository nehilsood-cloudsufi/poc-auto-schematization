# Stage 1: Build React frontend
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY tools/ tools/
COPY pyproject.toml .
COPY deploy/startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh

# Copy built frontend from Stage 1
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# Remove any stale bytecode from host (cross-platform safety)
RUN find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
RUN find /app -name "*.pyc" -delete 2>/dev/null; true

RUN mkdir -p /app/ui_output

ENV PYTHONPATH="/app:/app/src"
ENV PYTHONUNBUFFERED=1
ENV UI_OUTPUT_DIR="/app/ui_output"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/startup.sh"]
