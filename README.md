# Agent Identity Lab

Open-source reference implementation of an identity and authorization control plane for AI agents.

Agent Identity Lab demonstrates how autonomous agents can be represented as **first-class security principals** — with unique identities, short-lived credentials, delegated authority, policy-based authorization, identity-aware MCP tool access, token brokerage, and cryptographically verifiable audit records.

## Problem

Most AI agents authenticate using weak patterns (personal credentials, broad service accounts, static API keys) that fail to distinguish *which agent*, *which user*, *which runtime*, and *which permissions* were involved in any action.

## Architecture

```
Admin UI → Identity Control API → Policy Engine → Token Broker → MCP Gateway → Tools
                                                                       ↓
                                                                 PostgreSQL + Audit
```

## Quick Start

```bash
docker compose up -d
make demo-authorized-read
```

## Documentation

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
| 1 | Core Identity Model | 🔴 |
| 2 | Sessions and Tokens | 🔴 |
| 3 | Policy Enforcement | 🔴 |
| 4 | MCP Gateway | 🔴 |
| 5 | Token Brokerage | 🔴 |
| 6 | Audit and UI | 🔴 |
| 7 | Hermes Demo + Docs | 🔴 |

## License

MIT
