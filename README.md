# Agent Identity Lab

Open-source reference implementation of an identity and authorization control plane for AI agents.

Agent Identity Lab demonstrates how autonomous agents can be represented as **first-class security principals** — with unique identities, short-lived credentials, delegated authority, policy-based authorization, identity-aware MCP tool access, token brokerage, and cryptographically verifiable audit records.

🌐 **[Project Website →](https://rmax.ai/agent-identity-lab/)** — architecture, API reference, development phases, ADRs

## Problem

Most AI agents authenticate using weak patterns (personal credentials, broad service accounts, static API keys) that fail to distinguish *which agent*, *which user*, *which runtime*, and *which permissions* were involved in any action.

## Architecture

```
Identity API → Policy Engine → Token Broker → MCP Gateway → Tools
                                              ↓
                                        PostgreSQL + Audit
```

## Quick Start

```bash
# Install dependencies
uv sync --extra dev

# Generate dev keys
bash scripts/generate_dev_keys.sh

# Run services
docker compose up -d

# Run tests
PYTHONPATH=. uv run pytest tests/ -v

# Run demo (requires services running)
PYTHONPATH=. uv run python examples/delegated_research/authorized_read.py
```

## Run Without Docker

This repo can also be run locally without Docker for development and test execution.

```bash
# Install dependencies
uv sync --extra dev

# Generate dev keys
bash scripts/generate_dev_keys.sh

# Create a local SQLite database
PYTHONPATH=. DATABASE_URL=sqlite+aiosqlite:///./dev.sqlite3 uv run python scripts/init_local_db.py
```

Start each service in its own terminal:

```bash
PYTHONPATH=. DATABASE_URL=sqlite+aiosqlite:///./dev.sqlite3 JWT_PRIVATE_KEY_PATH=./keys/private.pem JWT_PUBLIC_KEY_PATH=./keys/public.pem uv run uvicorn apps.identity_api.main:app --host 127.0.0.1 --port 8000
```

```bash
PYTHONPATH=. DATABASE_URL=sqlite+aiosqlite:///./dev.sqlite3 uv run uvicorn apps.token_broker.main:app --host 127.0.0.1 --port 8001
```

```bash
PYTHONPATH=. JWT_PRIVATE_KEY_PATH=./keys/private.pem JWT_PUBLIC_KEY_PATH=./keys/public.pem IDENTITY_API_URL=http://127.0.0.1:8000 TOKEN_BROKER_URL=http://127.0.0.1:8001 MCP_GATEWAY_URL=http://127.0.0.1:8002 uv run uvicorn apps.mcp_gateway.main:app --host 127.0.0.1 --port 8002
```

```bash
PYTHONPATH=. uv run uvicorn apps.mock_mcp_server.main:app --host 127.0.0.1 --port 8003
```

Verify health:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8002/health
curl http://127.0.0.1:8003/health
```

Run tests locally without Docker:

```bash
PYTHONPATH=. uv run pytest tests/ -v
```

Notes:
- This local path uses SQLite for convenience instead of the default PostgreSQL Docker setup.
- Authorization falls back to the Python policy adapter when OPA is not running.
- The full production-like topology is still the Docker Compose flow.

## Example Scenarios

With the local stack running, you can execute the demo scenarios under `examples/`.

Authorized read:

```bash
PYTHONPATH=. uv run python examples/delegated_research/authorized_read.py
```

Example output:

```text
Demo: Authorized Read — decision=allow, scopes=['repo:read']
PASS: authorized read succeeded
```

Denied write:

```bash
PYTHONPATH=. uv run python examples/unauthorized_write_attempt/denied_write.py
```

Example output:

```text
Demo: Denied Write — decision=deny, reason=No scopes remain after intersection. Removed: ['issues:write']
PASS: unauthorized write attempt was denied
```

Suspended agent:

```bash
PYTHONPATH=. uv run python examples/hermes_agent/suspended_agent.py
```

Example output:

```text
Created initial session e7a6891d-96b1-4dba-bbc4-d3159eb5205b
Suspended agent 8102bd5b-1af7-4b6c-a1cf-4b5d07effbcc
PASS: suspended agent session creation failed with 400
```

Invalid runtime:

```bash
PYTHONPATH=. uv run python examples/hermes_agent/invalid_runtime.py
```

Example output:

```text
Demo: Invalid Runtime — decision=deny, reason=Environment 'development' not in approved environments
PASS: invalid runtime environment was denied
```

Secret isolation:

```bash
PYTHONPATH=. uv run python examples/delegated_research/secret_isolation.py
```

Example output:

```text
Demo: Secret Isolation — type=bearer, lease_id=87c4f9ef-f09f-40bb-b8dc-f38aec6ad20b
PASS: token broker returned a leased credential without raw secret material
```

Machine-only session:

```bash
PYTHONPATH=. uv run python examples/hermes_agent/machine_only_session.py
```

Example output:

```text
Demo: Machine-Only Session — decision=allow, acting_user=None
PASS: machine-only session authorized successfully
```

## Documentation

- 🌐 **[Project Website](https://rmax.ai/agent-identity-lab/)** — full site with architecture, API reference, phases, ADRs
- [Architecture](docs/architecture.md)
- [Threat Model](docs/threat-model.md)
- [Token Model](docs/token-model.md)
- [Policy Model](docs/policy-model.md)
- [MCP Integration](docs/mcp-integration.md)
- [Hermes Integration](docs/hermes-integration.md)
- [Demo Walkthrough](docs/demo.md)

## Development Phases

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Core Identity Model | ✅ |
| 2 | Sessions and Tokens | ✅ |
| 3 | Policy Enforcement | ✅ |
| 4 | MCP Gateway | ✅ |
| 5 | Token Brokerage | ✅ |
| 6 | Audit Chain | ✅ |
| 7 | Hermes Demo + Docs | ✅ |

## License

MIT
