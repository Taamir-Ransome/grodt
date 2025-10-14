FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml ./
COPY . .

# Install dependencies
RUN uv sync --frozen

# Create data directory
RUN mkdir -p /app/data

# Expose ports
EXPOSE 8000 9090

# Set environment variables
ENV PYTHONPATH=/app
ENV ENV=prod

# Run the application
CMD ["uv", "run", "python", "-m", "grodtd.app"]
