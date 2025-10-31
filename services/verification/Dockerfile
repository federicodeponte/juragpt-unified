# Multi-stage Dockerfile for JuraGPT Auditor
# Optimized for production deployment with model caching

# ==============================================================================
# Stage 1: Builder - Download models and install dependencies
# ==============================================================================
FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml ./
COPY src/ ./src/

# Set cache directories for model downloads
ENV HF_HOME=/models/huggingface
ENV TRANSFORMERS_CACHE=/models/transformers
ENV TORCH_HOME=/models/torch

# Install Python dependencies including PostgreSQL support
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[postgres]"

# Download spaCy model (German)
RUN python -m spacy download de_core_news_md

# Pre-download sentence-transformers model to specific cache location
# This ensures the model is cached and ready for use
RUN mkdir -p /models && \
    python -c "from sentence_transformers import SentenceTransformer; \
    model = SentenceTransformer('intfloat/multilingual-e5-large'); \
    print('Model downloaded successfully')"

# ==============================================================================
# Stage 2: Runtime - Minimal production image
# ==============================================================================
FROM python:3.11-slim

# Metadata
LABEL maintainer="JuraGPT Team"
LABEL description="Production-grade verification microservice for detecting hallucinations in LLM-generated legal answers"
LABEL version="1.0.0"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r auditor && \
    useradd -r -g auditor -s /bin/bash -m auditor

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy all downloaded models from builder
COPY --from=builder /models/ /home/auditor/.cache/

# Copy application code
COPY --chown=auditor:auditor src/ ./src/
COPY --chown=auditor:auditor config.yaml ./

# Set model cache directories for runtime
ENV TRANSFORMERS_CACHE=/home/auditor/.cache/transformers
ENV TORCH_HOME=/home/auditor/.cache/torch
ENV HF_HOME=/home/auditor/.cache/huggingface

# Ensure auditor user owns cache directory
RUN chown -R auditor:auditor /home/auditor/.cache

# Switch to non-root user
USER auditor

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Environment variables (can be overridden)
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV DATABASE_URL=sqlite:////app/data/auditor.db
ENV LOG_LEVEL=INFO

# Create data directory for SQLite (if using)
RUN mkdir -p /home/auditor/data

# Run the API server
CMD ["python", "-m", "uvicorn", "auditor.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
