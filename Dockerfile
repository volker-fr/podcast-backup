# Build stage
FROM python:3.12-slim AS builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy only dependency files first (for better layer caching)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies without installing the project itself
# This layer will be cached unless dependencies change
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code after dependencies are installed
# Changes to source code won't invalidate the dependency cache
COPY podcast_backup ./podcast_backup

# Install the project itself now that source code is available
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY podcast_backup ./podcast_backup
COPY pyproject.toml ./

# Fix permissions for non-root users
RUN find /app -type d -exec chmod 755 {} + && \
    find /app -type f -exec chmod 644 {} + && \
    find /app/.venv/bin -type f -exec chmod 755 {} +

# Set PATH to use venv
ENV PATH="/app/.venv/bin:$PATH"

# Create volume mount points
VOLUME ["/config", "/podcasts"]

# Run the CLI with config path
ENTRYPOINT ["podcast-backup"]
CMD ["--config", "/config/config.toml"]
