# Multi-stage build for GRODT trading system
# Stage 1: Build environment
FROM python:3.12-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies in virtual environment
RUN uv sync --frozen --no-dev

# Stage 2: Runtime environment
FROM python:3.12-slim as runtime

# Set working directory
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r grodt && useradd -r -g grodt grodt

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=grodt:grodt . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/logs /app/configs \
    && chown -R grodt:grodt /app

# Set proper file permissions
RUN chmod -R 755 /app \
    && chmod -R 777 /app/data /app/logs

# Switch to non-root user
USER grodt

# Set environment variables
ENV PYTHONPATH=/app
ENV ENV=prod
ENV PATH="/app/.venv/bin:$PATH"

# Expose ports
EXPOSE 8000 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "-m", "grodtd.web_app"]
