# Dockerfile for CAD-MATLAB Agent
# Note: This is a base image. FreeCAD and MATLAB must be added separately.

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agent/ ./agent/
COPY cad_templates/ ./cad_templates/
COPY matlab/ ./matlab/
COPY config.yaml ./

# Create runs directory
RUN mkdir -p /app/runs

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV ENV=production

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run API server
CMD ["python", "-m", "uvicorn", "agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

