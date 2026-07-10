# AGENTS.md — Agent Identity Lab

## Architecture

This is a monorepo with two layers:

- **packages/** — Shared libraries (no runtime, pure logic)
- **apps/** — Deployable services (FastAPI, each with its own main.py)

### Service Boundaries

| Service | Port | Responsibility |
|---------|------|----------------|
| identity_api | 8000 | Blueprints, agents, sessions, delegation, auth |
| token_broker | 8001 | Downstream credential issuance (no raw secret exposure) |
| mcp_gateway | 8002 | AuthN/Z proxy between agents and MCP servers |
| mock_mcp_server | 8003 | Test MCP server for development |
| admin_ui | 3000 | Next.js dashboard (planned post-MVP) |

### Data Flow

```
Agent → mcp_gateway → (auth check) → identity_api → policy_engine → token_broker → mcp_gateway → mock_mcp_server
                                                                                              ↓
                                                                                        audit log
```

### Key Design Decisions

- **Agents are first-class principals** (not service accounts) — ADR-001
- **JWT session tokens** with asymmetric signing — ADR-002
- **Permission intersection** (user ∩ agent ∩ blueprint ∩ tool ∩ env) — ADR-003
- **Server-side credential injection** — agents never see raw API keys — ADR-004
- **OPA for policy** with adapter interface — ADR-005
- **Tamper-evident audit chain** via hash chaining — ADR-006
- **Gateway as enforcement boundary** — no direct agent-to-tool access — ADR-007

## Tech Stack

- Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic
- PostgreSQL (Docker Compose)
- Open Policy Agent (OPA)
- Next.js + TypeScript + Tailwind (admin UI — planned post-MVP)
- Docker Compose for local dev

## Development

```bash
# Install
uv sync

# Run services
docker compose up -d

# Tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format --check .

# Type check
PYTHONPATH=. uv run ty check
```

## Testing Standards

- TDD: RED-GREEN-REFACTOR for all production code
- pytest + pytest-asyncio + aiosqlite (unit tests)
- PostgreSQL via Docker Compose (integration tests)
- Hypothesis for property-based policy/token invariants
- Playwright for UI tests (planned post-MVP)

## Commit Convention

Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
One logical change per commit. No WIP commits.
