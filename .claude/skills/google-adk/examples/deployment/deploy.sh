#!/bin/bash
# Deployment script for Google ADK agent to Cloud Run
# Reference: google_adk_python/llms.txt

set -e

# Configuration
PROJECT_ID="your-gcp-project-id"
SERVICE_NAME="adk-agent-service"
REGION="us-central1"
IMAGE_NAME="adk-agent"

echo "Deploying ADK Agent to Google Cloud Run"
echo "========================================"

# 1. Build Docker image
echo "Building Docker image..."
docker build -t gcr.io/$PROJECT_ID/$IMAGE_NAME:latest .

# 2. Push to Google Container Registry
echo "Pushing image to GCR..."
docker push gcr.io/$PROJECT_ID/$IMAGE_NAME:latest

# 3. Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$IMAGE_NAME:latest \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=$GEMINI_API_KEY \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0

echo "Deployment complete!"
echo "Service URL:"
gcloud run services describe $SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --format 'value(status.url)'