# Use prebuilt image with Python 3.12, uv, and Debian Bookworm slim
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Health check - test file server
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uv", "run", "file_server.py"]
