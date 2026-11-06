# ==============================================================================
# Dockerfile for Google Classroom to Discord Notifier
# ==============================================================================
# Multi-stage build for minimal image size and secure non-root execution
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build Dependencies
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ------------------------------------------------------------------------------
# Stage 2: Production Runtime
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Tokyo

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Create non-root user and group
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser && \
    mkdir -p /app/data /app/logs /app/config && \
    chown -R appuser:appuser /app

# Copy application source code
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser pyproject.toml /app/

# Switch to non-root user
USER appuser

# Healthcheck to verify process health
HEALTHCHECK --interval=60s --timeout=10s --start-period=10s --retries=3 \
    CMD ps aux | grep "[p]ython -m src.cli run --daemon" || exit 1

ENTRYPOINT ["python", "-m", "src.cli"]
CMD ["run", "--daemon"]
