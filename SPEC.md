# Agent Identity Lab — Software Project Specification

> Source: Original project specification, 2026-07-10
> Status: Complete — 24 sections covering architecture, API, security, and acceptance criteria

---

## 1. Project Summary

Agent Identity Lab is an open-source reference implementation of an identity and authorization control plane for AI agents.
The system demonstrates how autonomous agents can be represented as first-class security principals rather than running under shared service accounts, static API keys, or unrestricted human credentials.

It provides:
- Agent identity registration
- Blueprint-based provisioning
- Short-lived credentials
- User-to-agent delegation
- Policy-based authorization
- Identity-aware MCP tool access
- Token brokerage
- Lifecycle management
- Cryptographically verifiable audit records

The project is a proof of concept, not a production identity provider. Its purpose is to make the core architecture concrete, testable, and inspectable.

## 2. Problem Statement

Most AI agents currently authenticate using one of three weak patterns:
1. A developer's personal credentials.
2. A broad service account.
3. Static API keys stored in agent configuration.

These approaches fail to distinguish:
- Which agent acted
- Which user initiated the action
- Which runtime executed the agent
- Which model and code version were active
- Which permissions were intentionally delegated
- Which tool credentials were used
- Whether the action exceeded the agent's approved authority

**Central design requirement:**
Every state-changing tool call must be attributable to a specific agent identity, acting for a specific user, from a known runtime, under an explicit policy decision.

## 3. Goals

### 3.1 Primary Goals

The system must:
- Represent each deployed agent as a unique principal
- Issue short-lived credentials to agents
- Bind agent credentials to runtime metadata
- Distinguish agent identity from human identity
- Support user-delegated and machine-only execution
- Enforce least privilege at the tool-call boundary
- Integrate with MCP servers through a gateway
- Broker downstream credentials without exposing long-lived secrets
- Produce complete decision and execution audit trails
- Support provisioning, suspension, revocation, and decommissioning
- Demonstrate permission intersection between user, agent, tool, and environment

### 3.2 Secondary Goals

The system should:
- Remain vendor-neutral
- Use established standards where practical
- Run locally through Docker Compose
- Expose clear APIs and inspectable data models
- Support multiple policy engines through adapters
- Allow future integration with SPIFFE, OpenFGA, Cedar, OPA, and enterprise identity providers

## 4. Non-Goals

The first version will not:
- Replace Microsoft Entra ID, Okta, Auth0, Keycloak, or SPIRE
- Provide production-grade certificate authority operations
- Implement full enterprise identity governance
- Store model weights
- Evaluate model output quality
- Provide prompt-injection detection
- Implement complete human resource lifecycle synchronization
- Provide multi-region deployment
- Provide hardware-backed attestation
- Support every OAuth grant type
- Implement a full MCP client or server ecosystem

## 5. Core Concepts

### 5.1 Agent Blueprint

An Agent Blueprint defines the approved configuration for a class of agents.

Examples: Research Agent, Support Agent, Code Review Agent, Deployment Agent.

A blueprint defines: name, description, approved tools, maximum scopes, permitted environments, approved models, runtime requirements, credential lifetime, owner requirements, sponsor requirements, default policies.

A blueprint is a template, not an executable identity.

### 5.2 Agent Identity

An Agent Identity is a concrete principal created from a blueprint.

Each identity has: globally unique identifier, blueprint reference, lifecycle state, owner, sponsor, runtime metadata, allowed scopes, public key or certificate reference, creation timestamp, expiration or review timestamp.

Example URI: `agent://local/research-agent/01JXYZ...`

### 5.3 Acting User

The Acting User is the human or upstream identity on whose behalf the agent is operating. Optional for machine-only workloads.

### 5.4 Agent Session

An Agent Session is a short-lived execution context binding: agent identity, acting user, runtime, model, code version, policy context, issued credentials, trace identifier, expiration time.

### 5.5 Runtime Attestation

Runtime Attestation is the evidence describing where and how the agent is executing. The PoC uses signed runtime claims rather than hardware attestation.

Claims include: container image digest, Git commit, environment, host identifier, agent framework version, model identifier, prompt package version, timestamp.

### 5.6 Tool Resource

A Tool Resource is an MCP server, API, database, or external system that an agent may access.

Examples: GitHub, Jira, Confluence, local filesystem, internal search, email, calendar.

### 5.7 Delegation Grant

A Delegation Grant records the authority given by a human or upstream service to an agent.

Example: User Max delegates `github:repo:read` to ResearchAgent for 30 minutes.

### 5.8 Policy Decision

A Policy Decision determines whether an agent action is allowed.

**Effective authorization model:**
```
Effective Permission =
    User Permission
    ∩ Agent Permission
    ∩ Blueprint Permission
    ∩ Tool Permission
    ∩ Environment Policy
    ∩ Session Constraints
```

### 5.9 Token Broker

The Token Broker exchanges agent session credentials for scoped downstream credentials. The agent never receives long-lived API keys or refresh tokens directly.

### 5.10 Audit Record

An Audit Record captures: who acted, on whose behalf, from which runtime, against which tool, using which scope, under which policy, with which result.

## 6. Representative Use Case

A Research Agent is asked by a user to inspect a GitHub repository:

1. User authenticates.
2. User selects a registered Research Agent.
3. Identity service creates an Agent Session.
4. Runtime submits signed attestation claims.
5. Policy engine validates: user may access the repository, agent blueprint allows GitHub read access, agent identity is active, runtime is approved, requested scope is read-only.
6. Token Broker issues a short-lived GitHub credential.
7. Agent invokes the GitHub MCP tool through the MCP Gateway.
8. Gateway verifies the session and policy decision.
9. Downstream credential is injected server-side.
10. Request and result are written to the audit log.
11. The agent never receives the user's full GitHub credential.

## 7. Functional Requirements

### 7.1 Blueprint Management

The system must allow administrators to: create, update, version, activate, deactivate a blueprint; define maximum scopes, approved tools, approved models, permitted environments; assign default credential TTL; require owner and sponsor fields.

Example blueprint:
```yaml
id: research-agent
version: 1
name: Research Agent
description: Read-only technical research agent
approved_models:
  - openai:gpt-5-mini
  - deepseek:deepseek-chat
approved_environments:
  - development
  - staging
tools:
  - id: github
    scopes:
      - repo:read
      - issues:read
  - id: confluence
    scopes:
      - pages:read
session:
  max_ttl_seconds: 1800
runtime:
  require_container_digest: true
  require_git_commit: true
  require_signed_attestation: true
```

### 7.2 Agent Identity Management

The system must support: creating an agent identity from a blueprint, generating a unique identifier, assigning owner and sponsor, registering public key material, setting lifecycle state, rotating identity credentials, suspending, revoking, deleting/decommissioning, listing identities by blueprint/owner/sponsor/state.

**Lifecycle states:** draft, pending_approval, active, suspended, revoked, decommissioned.

Only active identities may create sessions.

### 7.3 Agent Session Creation

The system must accept a request containing: agent identity ID, acting user ID, requested scopes, runtime attestation, model identifier, prompt package version, requested TTL.

The system must: verify agent state, verify blueprint state, validate requested scopes, validate runtime claims, evaluate policy, create a session, issue a short-lived signed token, write an audit event.

Maximum MVP session lifetime: 30 minutes.

### 7.4 Runtime Attestation

The PoC must support software-based attestation. The runtime sends a signed attestation document:

```json
{
  "agent_id": "agt_01JXYZ",
  "container_digest": "sha256:abc123",
  "git_commit": "9b02f15",
  "environment": "development",
  "host_id": "docker-local-01",
  "framework": "hermes",
  "framework_version": "0.4.0",
  "model": "deepseek-chat",
  "prompt_version": "research-v3",
  "issued_at": "2026-07-10T16:00:00Z",
  "nonce": "random-value"
}
```

The attestation must be signed by the registered runtime key. The identity service must verify: signature, timestamp freshness, nonce uniqueness, agent ID match, required claim presence, blueprint constraints.

### 7.5 Delegation

The system must support two execution modes:

**User-delegated mode:** A human grants authority to the agent. Session token includes agent subject, acting user, delegation identifier, approved scopes.

**Machine-only mode:** The agent operates without a human initiator. Session token includes agent subject, workload purpose, approved machine scopes, no acting user claim.

User-delegated mode is required for actions involving personal user resources.

### 7.6 Policy Evaluation

The MVP must include a policy engine adapter. The default implementation may use OPA or a simple internal policy evaluator.

Policy inputs: agent, blueprint, user, session, runtime, tool, action, environment.

Policy output:
```json
{
  "decision": "allow",
  "reason": "User and agent both have repository read permission",
  "effective_scopes": ["repo:read"],
  "obligations": ["log_request", "redact_secrets"],
  "policy_version": "2026-07-10.1"
}
```

The policy engine must support: allow, deny, allow with reduced scopes, allow with obligations.

### 7.7 Token Brokerage

The Token Broker must: receive a valid Agent Session token, verify the requested tool and scopes, re-evaluate policy if needed, retrieve or generate downstream credentials, return a short-lived tool token or inject it directly, prevent agents from reading stored refresh tokens or API keys, log all credential issuance.

The MVP must implement at least two credential providers: Mock OAuth provider, Static secret provider with server-side injection.

Optional: GitHub OAuth or GitHub App token provider.

### 7.8 MCP Gateway

The MCP Gateway must sit between agents and MCP servers. Responsibilities: authenticate Agent Session tokens, extract agent and acting-user claims, identify requested MCP tool, map tool calls to required scopes, request a policy decision, obtain downstream credentials, inject credentials, forward the request, capture response metadata, write audit events, reject unauthorized requests.

Example request:
```
POST /mcp/tools/github.search_code
Authorization: Bearer <agent-session-token>
X-Agent-Trace-ID: trace_123
```

Example policy mapping:
```yaml
github.search_code:
  required_scopes:
    - repo:read

github.create_issue:
  required_scopes:
    - issues:write
```

### 7.9 Audit Logging

The system must record these events: blueprint created/updated, agent registered/activated/suspended/revoked, session requested/approved/denied, runtime attestation accepted/rejected, tool authorization allowed/denied, downstream credential issued, tool invocation completed/failed.

Each event must include:
```json
{
  "event_id": "evt_01JXYZ",
  "event_type": "tool.authorization.allowed",
  "timestamp": "2026-07-10T16:05:00Z",
  "agent_id": "agt_01JXYZ",
  "acting_user_id": "usr_123",
  "session_id": "ses_456",
  "trace_id": "trace_789",
  "tool_id": "github",
  "operation": "search_code",
  "requested_scopes": ["repo:read"],
  "effective_scopes": ["repo:read"],
  "policy_version": "2026-07-10.1",
  "runtime_digest": "sha256:abc123",
  "decision": "allow",
  "reason": "Permission intersection satisfied"
}
```

### 7.10 Tamper-Evident Audit Chain

The PoC must support append-only hash chaining:

```
record_hash = SHA256(previous_hash + canonical_event_json)
```

This provides tamper evidence without requiring a blockchain. The system must expose an endpoint to verify the audit chain.

### 7.11 Administrative UI

The UI must provide: Dashboard (total identities, active/suspended, active sessions, denied actions, credentials issued, recent audit events), Blueprint view (metadata, version, tools, scopes, models, associated identities), Agent identity view (status, owner, sponsor, blueprint, registered keys, recent sessions, revoke/suspend buttons), Session view (acting user, model, runtime, effective scopes, issued credentials, expiration, policy decisions, trace timeline), Audit explorer (filters: agent, user, tool, action, decision, session, date range, trace ID).

## 8. System Architecture

```
┌─────────────────────────────────────────────┐
│                 Admin UI                    │
└──────────────────────┬──────────────────────┘
                       │
┌──────────────────────▼──────────────────────┐
│            Identity Control API             │
│  Blueprint Service · Agent Registry         │
│  Session Service · Lifecycle Service        │
└───────────────┬─────────────────────────────┘
                │
       ┌────────▼─────────┐
       │ Policy Engine    │
       └────────┬─────────┘
                │
       ┌────────▼─────────┐
       │ Token Broker     │
       └────────┬─────────┘
                │
┌───────────────▼─────────────────────────────┐
│             MCP Gateway                     │
│  AuthN · AuthZ · Cred Injection · Audit     │
└───────────────┬─────────────────────────────┘
                │
        ┌───────▼────────┐
        │ MCP Servers    │
        │ External APIs  │
        └────────────────┘

All services write to:
┌─────────────────────────────────────────────┐
│ PostgreSQL · Audit Event Store              │
│ Secret Vault Adapter                        │
└─────────────────────────────────────────────┘
```

## 9. Recommended Technology Stack

### 9.1 Backend
- Language: Python 3.13 (targeting 3.12+)
- Framework: FastAPI
- Validation: Pydantic v2
- ORM: SQLAlchemy 2
- Migrations: Alembic
- Database: PostgreSQL
- Authentication: Authlib or PyJWT
- Cryptography: cryptography
- HTTP client: httpx
- Task execution: built-in async tasks initially

### 9.2 Policy Engine
- Preferred: Open Policy Agent (OPA)
- Fallback for MVP: Python policy adapter with declarative YAML rules
- The policy API must remain adapter-based

### 9.3 Secrets
- Local development: encrypted database fields or Docker secrets
- Preferred extension: HashiCorp Vault

### 9.4 Frontend
- Next.js, TypeScript, React, Tailwind CSS
- The UI should remain operational and diagnostic rather than marketing-oriented

### 9.5 Infrastructure
- Docker Compose with PostgreSQL, OPA, Identity API, Token Broker, MCP Gateway, Mock MCP Server, Admin UI

### 9.6 Testing
- pytest, pytest-asyncio, Testcontainers, Hypothesis (for policy and token invariants), Playwright (for UI tests)

## 10. Repository Structure

```
agent-identity-lab/
├── README.md
├── LICENSE
├── pyproject.toml
├── docker-compose.yml
├── Makefile
├── .env.example
├── apps/
│   ├── identity_api/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── domain/
│   │   ├── services/
│   │   ├── repositories/
│   │   └── schemas/
│   ├── token_broker/
│   │   ├── main.py
│   │   ├── providers/
│   │   └── services/
│   ├── mcp_gateway/
│   │   ├── main.py
│   │   ├── middleware/
│   │   ├── tool_registry/
│   │   └── proxy/
│   ├── mock_mcp_server/
│   │   ├── main.py
│   │   └── tools/
│   └── admin_ui/
├── packages/
│   ├── identity_models/
│   ├── token_library/
│   ├── attestation/
│   ├── audit/
│   ├── policy_client/
│   └── common/
├── policies/
│   ├── agent_access.rego
│   ├── tool_access.rego
│   └── examples/
├── blueprints/
│   ├── research-agent.yaml
│   ├── support-agent.yaml
│   └── deployment-agent.yaml
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── security/
│   └── e2e/
├── examples/
│   ├── hermes_agent/
│   ├── delegated_research/
│   └── unauthorized_write_attempt/
└── docs/
    ├── architecture.md
    ├── threat-model.md
    ├── token-model.md
    ├── policy-model.md
    ├── mcp-integration.md
    └── demo.md
```

## 11. Domain Model

### 11.1 AgentBlueprint

```python
class AgentBlueprint:
    id: UUID
    slug: str
    version: int
    name: str
    description: str
    status: BlueprintStatus
    approved_models: list[str]
    approved_environments: list[str]
    max_scopes: list[str]
    tool_permissions: dict[str, list[str]]
    max_session_ttl_seconds: int
    runtime_requirements: dict
    created_at: datetime
    updated_at: datetime
```

### 11.2 AgentIdentity

```python
class AgentIdentity:
    id: UUID
    principal_uri: str
    blueprint_id: UUID
    owner_id: str
    sponsor_id: str
    status: AgentStatus
    public_key: str
    metadata: dict
    created_at: datetime
    activated_at: datetime | None
    suspended_at: datetime | None
    revoked_at: datetime | None
```

### 11.3 DelegationGrant

```python
class DelegationGrant:
    id: UUID
    user_id: str
    agent_id: UUID
    scopes: list[str]
    resource_constraints: dict
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
```

### 11.4 AgentSession

```python
class AgentSession:
    id: UUID
    agent_id: UUID
    acting_user_id: str | None
    delegation_grant_id: UUID | None
    model_id: str
    prompt_version: str
    runtime_attestation_id: UUID
    requested_scopes: list[str]
    effective_scopes: list[str]
    policy_version: str
    trace_id: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
```

### 11.5 RuntimeAttestation

```python
class RuntimeAttestation:
    id: UUID
    agent_id: UUID
    container_digest: str
    git_commit: str
    environment: str
    host_id: str
    framework: str
    framework_version: str
    model_id: str
    prompt_version: str
    nonce: str
    signature: str
    issued_at: datetime
    verified_at: datetime | None
    verification_result: str
```

### 11.6 ToolDefinition

```python
class ToolDefinition:
    id: UUID
    slug: str
    protocol: str
    endpoint: str
    operations: dict[str, list[str]]
    credential_provider: str
    enabled: bool
```

### 11.7 CredentialLease

```python
class CredentialLease:
    id: UUID
    session_id: UUID
    tool_id: UUID
    scopes: list[str]
    provider: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
```

No raw credential value may be stored in this record.

### 11.8 AuditEvent

```python
class AuditEvent:
    id: UUID
    event_type: str
    timestamp: datetime
    agent_id: UUID | None
    acting_user_id: str | None
    session_id: UUID | None
    trace_id: str | None
    tool_id: UUID | None
    operation: str | None
    decision: str | None
    reason: str | None
    data: dict
    previous_hash: str | None
    record_hash: str
```

## 12. Token Model

### 12.1 Agent Session Token

Use a signed JWT for the PoC.

Required claims:
```json
{
  "iss": "agent-identity-lab",
  "sub": "agent:agt_01JXYZ",
  "aud": "mcp-gateway",
  "iat": 1783700000,
  "exp": 1783701800,
  "jti": "ses_456",
  "agent_id": "agt_01JXYZ",
  "blueprint_id": "research-agent:v1",
  "acting_user": "usr_123",
  "delegation_id": "dlg_789",
  "scopes": ["repo:read"],
  "runtime_digest": "sha256:abc123",
  "model": "deepseek-chat",
  "prompt_version": "research-v3",
  "trace_id": "trace_123",
  "policy_version": "2026-07-10.1"
}
```

### 12.2 Token Security Requirements

- Asymmetric signing
- Maximum 30-minute lifetime
- Unique token identifier (jti)
- Explicit audience
- Revocation support through session lookup
- Key rotation support
- No secrets in token claims
- Reject unsigned tokens
- Reject algorithm substitution
- Reject expired tokens
- Reject wrong audience
- Reject inactive agent identities

## 13. API Specification

### 13.1 Blueprints

```
POST   /v1/blueprints
GET    /v1/blueprints
GET    /v1/blueprints/{id}
PUT    /v1/blueprints/{id}
POST   /v1/blueprints/{id}/activate
POST   /v1/blueprints/{id}/deactivate
```

### 13.2 Agent Identities

```
POST   /v1/agents
GET    /v1/agents
GET    /v1/agents/{id}
POST   /v1/agents/{id}/activate
POST   /v1/agents/{id}/suspend
POST   /v1/agents/{id}/revoke
POST   /v1/agents/{id}/rotate-key
```

### 13.3 Delegation

```
POST   /v1/delegations
GET    /v1/delegations/{id}
POST   /v1/delegations/{id}/revoke
```

### 13.4 Sessions

```
POST   /v1/sessions
GET    /v1/sessions/{id}
POST   /v1/sessions/{id}/revoke
```

Session creation request:
```json
{
  "agent_id": "agt_01JXYZ",
  "acting_user_id": "usr_123",
  "delegation_grant_id": "dlg_789",
  "requested_scopes": ["repo:read"],
  "requested_ttl_seconds": 900,
  "model_id": "deepseek-chat",
  "prompt_version": "research-v3",
  "runtime_attestation": {}
}
```

### 13.5 Authorization

```
POST /v1/authorize
```

Request:
```json
{
  "session_token": "...",
  "tool": "github",
  "operation": "search_code",
  "resource": {
    "repository": "rmax-ai/example"
  }
}
```

Response:
```json
{
  "decision": "allow",
  "effective_scopes": ["repo:read"],
  "reason": "Permission intersection satisfied",
  "decision_id": "dec_123",
  "obligations": ["log_request"]
}
```

### 13.6 Token Broker

```
POST /v1/token-exchange
```

The endpoint should be callable only by trusted infrastructure such as the MCP Gateway.

### 13.7 Audit

```
GET  /v1/audit/events
GET  /v1/audit/events/{id}
POST /v1/audit/verify-chain
```

## 14. Policy Examples

### 14.1 Allow read operation

```rego
allow if {
  input.agent.status == "active"
  input.blueprint.status == "active"
  input.tool.id == "github"
  input.action.operation == "search_code"
  "repo:read" in input.agent.scopes
  "repo:read" in input.user.scopes
  input.runtime.environment in input.blueprint.approved_environments
}
```

### 14.2 Deny write operation for research agent

```rego
deny_reason := "Research agents cannot modify repositories" if {
  input.blueprint.slug == "research-agent"
  endswith(input.action.required_scope, ":write")
}
```

### 14.3 Reduce scopes

Requested: `repo:read, issues:read, issues:write`
Effective: `repo:read, issues:read`

The policy decision should explicitly record the removed scope.

## 15. Security Requirements

### 15.1 Threats to Address

The PoC threat model must include:
- Stolen bearer token
- Replayed runtime attestation
- Compromised agent runtime
- Overprivileged service account
- Prompt injection causing unauthorized tool calls
- Confused deputy behavior
- Forged acting-user identity
- Unauthorized scope escalation
- Credential leakage
- Revoked identity continuing to act
- Audit log tampering
- Tool mapping bypass
- Token audience confusion
- Stale blueprint configuration

### 15.2 Required Controls

- Short-lived session credentials
- Strict token audience validation
- Agent lifecycle validation on each sensitive request
- Nonce-based attestation replay prevention
- Server-side secret injection
- Scope intersection
- Explicit tool-to-scope mapping
- Deny by default
- Append-only audit chain
- Structured authorization reasons
- Trace propagation
- Credential lease expiration
- Session revocation
- Key rotation
- Request size limits
- Rate limiting
- Secret redaction from logs

### 15.3 Fail-Closed Behavior

The system must deny access when:
- The policy service is unavailable
- Attestation verification fails
- Tool mapping is missing
- Agent status cannot be verified
- Token broker cannot determine effective scopes
- Credential provider returns an ambiguous result

## 16. Demonstration Scenarios

### 16.1 Scenario A: Authorized read access

A Research Agent reads files from an approved repository.

Expected result: session created, policy allows read scope, token broker issues read-only credential, MCP request succeeds, complete trace appears in audit UI.

### 16.2 Scenario B: Unauthorized write attempt

The same agent attempts to create a GitHub issue.

Expected result: policy denies the action, no downstream credential is issued, gateway returns HTTP 403, denial reason appears in audit log.

### 16.3 Scenario C: User lacks permission

The agent has repository-read permission, but the acting user does not.

Expected result: permission intersection fails, request denied.

### 16.4 Scenario D: Suspended identity

An administrator suspends the agent during an active session.

Expected result: subsequent tool calls fail, existing session is treated as invalid, audit event records the lifecycle-based denial.

### 16.5 Scenario E: Invalid runtime

The agent runs from an unapproved container digest.

Expected result: session creation denied, no session token issued, attestation rejection logged.

### 16.6 Scenario F: Secret isolation

A tool call requires an external API key.

Expected result: the agent receives no raw key, the gateway injects the key, logs contain only credential lease metadata.

## 17. Hermes Integration

Hermes should integrate through a small identity client library.

Before executing a plan, Hermes:
1. Loads its Agent Identity ID
2. Creates runtime attestation
3. Requests an Agent Session
4. Stores the short-lived session token in memory
5. Attaches the token to MCP gateway requests
6. Propagates a trace ID across the entire run

Example client interface:
```python
class AgentIdentityClient:
    async def create_session(
        self,
        agent_id: str,
        acting_user_id: str | None,
        requested_scopes: list[str],
        runtime_attestation: RuntimeAttestation,
        model_id: str,
        prompt_version: str,
    ) -> AgentSession:
        ...
```

Hermes execution plans should declare required authority before execution:
```yaml
plan_id: plan_123
agent_id: research-agent-01
requested_tools:
  - tool: github.search_code
    scopes:
      - repo:read
  - tool: confluence.search
    scopes:
      - pages:read
```

This enables preflight authorization before expensive model execution.

## 18. Testing Strategy

### 18.1 Unit Tests

Test: scope intersection, token validation, lifecycle transitions, attestation verification, hash-chain generation, policy adapter behavior, tool-to-scope mapping, credential expiration.

### 18.2 Integration Tests

Test: identity API with PostgreSQL, policy service integration, token broker with mock provider, gateway with mock MCP server, session revocation propagation, audit chain verification.

### 18.3 Security Tests

Test: expired token, wrong audience, forged signature, replayed nonce, revoked agent, suspended blueprint, scope escalation, unregistered tool, missing acting user, credential leakage into logs.

### 18.4 Property-Based Tests

Useful invariants:
- Effective scopes must always be a subset of requested scopes
- Effective scopes must always be a subset of agent scopes
- Effective scopes must always be a subset of blueprint scopes
- A revoked identity must never receive a valid session
- A denied action must never create a credential lease

### 18.5 End-to-End Tests

Each demonstration scenario must be executable through one command:
```bash
make demo-authorized-read
make demo-denied-write
make demo-suspended-agent
make demo-invalid-runtime
make demo-secret-isolation
```

## 19. Observability

The system should expose: structured JSON logs, request IDs, session IDs, trace IDs, decision IDs, Prometheus-compatible metrics, OpenTelemetry traces.

Core metrics:
- `agent_sessions_created_total`
- `agent_sessions_denied_total`
- `tool_authorizations_allowed_total`
- `tool_authorizations_denied_total`
- `credential_leases_created_total`
- `credential_leases_active`
- `attestation_failures_total`
- `policy_evaluation_duration_seconds`
- `gateway_request_duration_seconds`

## 20. Development Phases

| Phase | Name | Scope |
|-------|------|-------|
| 1 | Core Identity Model | PostgreSQL schema, blueprint API, agent API, lifecycle state machine, basic admin auth, unit tests |
| 2 | Sessions and Tokens | Runtime attestation, signed JWT session tokens, delegation grants, token validation, revocation, session audit events |
| 3 | Policy Enforcement | Policy adapter interface, OPA integration, scope intersection, allow/deny decisions, policy reason logging |
| 4 | MCP Gateway | Gateway proxy, tool registry, tool-to-scope mappings, authorization middleware, mock MCP server, trace propagation |
| 5 | Token Brokerage | Provider interface, mock OAuth provider, static secret injection, credential leases, secret redaction tests |
| 6 | Audit and UI | Tamper-evident audit chain, audit verification, dashboard, agent detail, session timeline, denial explorer |
| 7 | Hermes Demo + Docs | Python client SDK, Hermes integration example, typed execution-plan authorization, end-to-end demos, architecture docs |

## 21. MVP Acceptance Criteria

The MVP is complete when:
1. An administrator can create a blueprint
2. An administrator can create and activate an agent identity
3. A runtime can submit signed attestation
4. An active agent can obtain a short-lived session token
5. The session token identifies both agent and acting user
6. The gateway can authorize an MCP tool call
7. Effective permissions are computed through intersection
8. A downstream credential can be injected without exposure to the agent
9. An unauthorized write attempt is denied
10. Suspending an identity blocks subsequent calls
11. Every decision appears in the audit log
12. The audit hash chain can be verified
13. The full system runs through Docker Compose
14. The main scenarios are covered by automated end-to-end tests

## 22. Stretch Goals

After the MVP:
- SPIFFE and SPIRE integration
- mTLS-bound credentials
- DPoP support
- OAuth Token Exchange
- OpenFGA relationship-based authorization
- Cedar policy adapter
- HashiCorp Vault provider
- GitHub App provider
- Keycloak integration
- Microsoft Entra Agent ID adapter
- Google workload identity adapter
- Agent-to-agent delegation
- Nested delegation chains
- Proof-carrying tool actions
- Signed execution plans
- Approval workflows for high-risk actions
- Policy simulation before execution
- Identity-aware agent evaluation
- Anomaly detection across agent behavior
- SCIM provisioning
- Periodic sponsor reviews
- Automatic identity expiration
- Cross-organization agent federation

## 23. Documentation Deliverables

The repository must include:
- Architecture overview
- Threat model
- Identity and token model
- Policy model
- MCP gateway integration guide
- Hermes integration guide
- Local setup instructions
- Demonstration walkthrough
- Security limitations
- Production hardening recommendations
- Architecture decision records

Required ADRs:
- ADR-001: Agents as first-class principals
- ADR-002: JWT session credentials
- ADR-003: Permission intersection model
- ADR-004: Server-side credential injection
- ADR-005: OPA policy adapter
- ADR-006: Tamper-evident audit chain
- ADR-007: MCP gateway enforcement boundary

## 24. Success Criteria

The project succeeds if an engineer can inspect a single agent action and answer:
- Which agent performed it?
- Which blueprint authorized that agent?
- Which user initiated or delegated it?
- Which runtime executed it?
- Which model and prompt version were active?
- Which permissions were requested?
- Which permissions were actually granted?
- Which policy produced the decision?
- Which downstream credential was used?
- Which tool operation was called?
- Whether the agent or session was later revoked?
- Whether the audit record has been modified?

The broader result should demonstrate that agent identity is not merely another service-account label. It is the security boundary that connects autonomous reasoning, user delegation, runtime trust, tool authorization, and enterprise accountability.
