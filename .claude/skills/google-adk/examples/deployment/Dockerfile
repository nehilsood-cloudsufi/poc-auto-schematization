# Dockerfile for deploying Google ADK Python agents
# Reference: google_adk_python/llms.txt - Deploy Anywhere section

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (for Cloud Run or other services)
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Run the agent application
CMD ["python", "main.py"]