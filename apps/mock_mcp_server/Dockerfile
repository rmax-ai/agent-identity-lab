FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
COPY packages/ ./packages/
COPY apps/mock_mcp_server/ ./apps/mock_mcp_server/

RUN uv sync --frozen || uv sync

EXPOSE 8003

CMD ["uv", "run", "uvicorn", "apps.mock_mcp_server.main:app", "--host", "0.0.0.0", "--port", "8003"]
