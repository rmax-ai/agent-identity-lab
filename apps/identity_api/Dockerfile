FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for psycopg2/asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock* ./
COPY packages/ ./packages/
COPY apps/identity_api/ ./apps/identity_api/
COPY apps/token_broker/ ./apps/token_broker/
COPY apps/mcp_gateway/ ./apps/mcp_gateway/

# Install dependencies
RUN uv sync --frozen || uv sync

# Generate dev keys if not present
RUN mkdir -p /keys && \
    if [ ! -f /keys/private.pem ]; then \
        openssl genpkey -algorithm RSA -out /keys/private.pem -pkeyopt rsa_keygen_bits:2048 && \
        openssl rsa -pubout -in /keys/private.pem -out /keys/public.pem; \
    fi

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "apps.identity_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
