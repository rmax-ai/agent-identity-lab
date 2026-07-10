FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
COPY packages/ ./packages/
COPY apps/mcp_gateway/ ./apps/mcp_gateway/
COPY apps/identity_api/ ./apps/identity_api/

RUN uv sync --frozen || uv sync

EXPOSE 8002

CMD ["uv", "run", "uvicorn", "apps.mcp_gateway.main:app", "--host", "0.0.0.0", "--port", "8002"]
