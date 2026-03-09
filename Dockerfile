# Phemex Trading Bot - Docker Image
# Multi-stage build for optimal size and security

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PROFILE=local_paper

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Set working directory
WORKDIR /app

# Copy requirements first (for better layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code and required runtime assets
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY models/ ./models/
COPY config.json .

# Create persistent directories (state/ for encrypted state files)
RUN mkdir -p /app/data /app/logs /app/state

# Change ownership to non-root user
RUN chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 src/healthcheck.py --profile ${PROFILE:-local_paper} || exit 1

# Default command (override --profile via docker-compose command:)
CMD ["python3", "-m", "src.run_bot", "--profile", "local_paper"]