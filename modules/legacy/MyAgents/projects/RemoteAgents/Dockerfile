# Dockerfile for Agent Remote Relay Service
# This container runs the relay server for testing network disconnect scenarios

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml /app/
COPY src/ /app/src/

# Install Python dependencies
# Using pip to install the package in editable mode
RUN pip install --no-cache-dir -e .

# Set environment variables for relay service
ENV RELAY_HOST=0.0.0.0
ENV RELAY_PORT=8080
ENV LOG_LEVEL=INFO
ENV CLEANUP_INTERVAL=60

# Expose the relay port
EXPOSE 8080

# Health check to verify the relay service is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health').read()" || exit 1

# Run the relay server
CMD ["python", "-m", "agent_remote.services.relay.api.server"]
