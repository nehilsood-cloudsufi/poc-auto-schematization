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

RUN mkdir -p /app/ui_output

ENV PYTHONPATH="/app:/app/src"
ENV PYTHONUNBUFFERED=1
ENV UI_OUTPUT_DIR="/app/ui_output"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080/_stcore/health || exit 1

ENTRYPOINT ["/app/startup.sh"]
