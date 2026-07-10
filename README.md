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
