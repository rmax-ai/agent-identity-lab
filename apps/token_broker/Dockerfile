FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
COPY packages/ ./packages/
COPY apps/token_broker/ ./apps/token_broker/
COPY apps/identity_api/ ./apps/identity_api/

RUN uv sync --frozen || uv sync

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "apps.token_broker.main:app", "--host", "0.0.0.0", "--port", "8001"]
