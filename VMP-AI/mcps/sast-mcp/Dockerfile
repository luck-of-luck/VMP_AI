FROM python:3.12-slim AS base

# Install system dependencies for Bearer
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Bearer CLI
RUN curl -sfL https://raw.githubusercontent.com/Bearer/bearer/main/contrib/install.sh | sh

# Set up Python environment
WORKDIR /app

# Install Python package and scanner dependencies
COPY pyproject.toml README.md LICENSE ./
COPY sast_mcp_server/ ./sast_mcp_server/

RUN pip install --no-cache-dir . bandit njsscan

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash scanner
USER scanner

# Default: run the MCP server in stdio mode
ENTRYPOINT ["sast-mcp-server"]
