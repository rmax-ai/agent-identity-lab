# Agent Identity Lab — Implementation Plan

> **For Hermes:** Use subagent-driven-development or Codex CLI to implement this plan task-by-task.
> Each phase builds on the previous. Phases are sequential within, but tasks within a phase can be parallelized where noted.

**Goal:** Build an open-source identity and authorization control plane for AI agents — agents as first-class security principals with blueprints, sessions, policy intersection, MCP gateway, token brokerage, and tamper-evident audit.

**Architecture:** Monorepo with shared packages (identity_models, token_library, attestation, audit, policy_client, common) and deployable apps (identity_api, token_broker, mcp_gateway, mock_mcp_server, admin_ui). FastAPI + Pydantic v2 + SQLAlchemy 2 + PostgreSQL + OPA. Docker Compose local dev.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic, PostgreSQL, OPA, Authlib/PyJWT, httpx, Next.js + TypeScript + Tailwind

---

## Acceptance Criteria (MVP)

- [ ] Admin can create, update, version, activate, and deactivate blueprints
- [ ] Admin can create, activate, suspend, revoke, and rotate keys for agent identities
- [ ] Runtime can submit signed attestation; identity service verifies it
- [ ] Active agent can obtain a short-lived JWT session token (max 30min)
- [ ] Session token identifies both agent and acting user (user-delegated mode)
- [ ] Machine-only sessions work without acting_user claim
- [ ] MCP Gateway authenticates session tokens and authorizes tool calls
- [ ] Effective permissions computed via intersection (user ∩ agent ∩ blueprint ∩ tool ∩ env)
- [ ] Token broker issues downstream credentials without exposing raw secrets to agent
- [ ] Unauthorized write attempt denied with 403 + audit log
- [ ] Suspending an identity blocks subsequent tool calls
- [ ] Every decision appears in tamper-evident audit log
- [ ] Audit hash chain verifiable via `/v1/audit/verify-chain`
- [ ] All 6 demo scenarios pass via `make demo-*`
- [ ] Full system runs via `docker compose up`
- [ ] All unit, integration, security, and property-based tests pass
- [ ] Lint, format, and type check pass clean

---

## Phase 1: Core Identity Model

**Deliver:** PostgreSQL schema, blueprint API, agent identity API, lifecycle state machine, basic admin auth, unit tests.

### Task 1.1: Project scaffold — packages and Alembic config

**Objective:** Set up shared packages structure, pyproject.toml dependencies, Alembic.

**Files:**
- Modify: `pyproject.toml`
- Create: `packages/identity_models/__init__.py`
- Create: `packages/token_library/__init__.py`
- Create: `packages/attestation/__init__.py`
- Create: `packages/audit/__init__.py`
- Create: `packages/policy_client/__init__.py`
- Create: `packages/common/models.py` (Base, TimestampMixin)
- Create: `apps/identity_api/__init__.py`
- Create: `apps/identity_api/main.py` (FastAPI app skeleton)
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/script.py.mako`

**Step 1:** Add dependencies to pyproject.toml:
```toml
[project]
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "authlib>=1.3.0",
    "pyjwt>=2.8.0",
    "cryptography>=42.0.0",
    "httpx>=0.27.0",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "testcontainers>=4.5.0",
    "hypothesis>=6.100.0",
    "httpx>=0.27.0",
    "ruff>=0.4.0",
]
```

**Step 2:** Run `uv sync` to install deps.

**Step 3:** Run `uv run alembic init migrations` then fix `alembic.ini` sqlalchemy.url to read from env.

**Step 4:** Verify: `uv run python -c "import fastapi; import sqlalchemy; import alembic; print('OK')"`

---

### Task 1.2: Base models — TimestampMixin, enums, UUID patterns

**Objective:** Create shared base model and enums.

**Files:**
- Create: `packages/common/models.py`
- Create: `packages/common/enums.py`

**Code:**

```python
# packages/common/models.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
```

```python
# packages/common/enums.py
from enum import StrEnum


class BlueprintStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class AgentStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    DECOMMISSIONED = "decommissioned"


class VerificationResult(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class ExecutionMode(StrEnum):
    USER_DELEGATED = "user_delegated"
    MACHINE_ONLY = "machine_only"
```

**Test:**
```python
# tests/unit/test_enums.py
def test_agent_status_values():
    assert AgentStatus.ACTIVE.value == "active"
    assert AgentStatus.SUSPENDED.value == "suspended"
```

---

### Task 1.3: AgentBlueprint model + schema

**Objective:** Create the AgentBlueprint SQLAlchemy model and Pydantic schemas.

**Files:**
- Create: `packages/identity_models/blueprint.py`
- Create: `packages/identity_models/schemas.py` (BlueprintCreate, BlueprintResponse)

**Model:**
```python
# packages/identity_models/blueprint.py
from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from packages.common.models import Base, TimestampMixin, new_uuid
from packages.common.enums import BlueprintStatus


class AgentBlueprint(Base, TimestampMixin):
    __tablename__ = "agent_blueprints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[BlueprintStatus] = mapped_column(String(32), default=BlueprintStatus.DRAFT)
    approved_models: Mapped[list] = mapped_column(JSONB, default=list)
    approved_environments: Mapped[list] = mapped_column(JSONB, default=list)
    max_scopes: Mapped[list] = mapped_column(JSONB, default=list)
    tool_permissions: Mapped[dict] = mapped_column(JSONB, default=dict)
    max_session_ttl_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    runtime_requirements: Mapped[dict] = mapped_column(JSONB, default=dict)
```

**Schema:**
```python
# packages/identity_models/schemas.py
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from packages.common.enums import BlueprintStatus


class BlueprintCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    approved_models: list[str] = Field(default_factory=list)
    approved_environments: list[str] = Field(default_factory=list)
    max_scopes: list[str] = Field(default_factory=list)
    tool_permissions: dict[str, list[str]] = Field(default_factory=dict)
    max_session_ttl_seconds: int = Field(ge=60, le=86400, default=1800)
    runtime_requirements: dict = Field(default_factory=dict)


class BlueprintResponse(BaseModel):
    id: UUID
    slug: str
    version: int
    name: str
    description: str | None
    status: BlueprintStatus
    approved_models: list[str]
    approved_environments: list[str]
    max_scopes: list[str]
    tool_permissions: dict[str, list[str]]
    max_session_ttl_seconds: int
    runtime_requirements: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

**Test:** Write a unit test that creates a BlueprintCreate, validates it passes Pydantic validation, and verifies defaults.

Run: `pytest tests/unit/test_blueprint_schemas.py -v`
Expected: 1 PASS

---

### Task 1.4: Blueprint repository

**Objective:** SQLAlchemy repository for CRUD operations on blueprints.

**Files:**
- Create: `apps/identity_api/repositories/__init__.py`
- Create: `apps/identity_api/repositories/blueprint_repo.py`

**Code:**
```python
# apps/identity_api/repositories/blueprint_repo.py
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.identity_models.blueprint import AgentBlueprint


class BlueprintRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, blueprint: AgentBlueprint) -> AgentBlueprint:
        self.session.add(blueprint)
        await self.session.commit()
        await self.session.refresh(blueprint)
        return blueprint

    async def get_by_id(self, id: UUID) -> AgentBlueprint | None:
        return await self.session.get(AgentBlueprint, id)

    async def get_by_slug(self, slug: str) -> AgentBlueprint | None:
        result = await self.session.execute(
            select(AgentBlueprint).where(AgentBlueprint.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[AgentBlueprint]:
        result = await self.session.execute(select(AgentBlueprint))
        return list(result.scalars().all())

    async def update(self, blueprint: AgentBlueprint) -> AgentBlueprint:
        await self.session.commit()
        await self.session.refresh(blueprint)
        return blueprint
```

**Test:** Integration test with testcontainers PostgreSQL.

Run: `pytest tests/integration/test_blueprint_repo.py -v`
Expected: 3-4 PASS

---

### Task 1.5: Blueprint API endpoints

**Objective:** FastAPI routes for blueprint CRUD.

**Files:**
- Create: `apps/identity_api/api/__init__.py`
- Create: `apps/identity_api/api/blueprints.py`
- Modify: `apps/identity_api/main.py` (register router)

**Code (blueprints.py):**
```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from packages.identity_models.schemas import BlueprintCreate, BlueprintResponse
from packages.identity_models.blueprint import AgentBlueprint
from apps.identity_api.repositories.blueprint_repo import BlueprintRepository

router = APIRouter(prefix="/v1/blueprints", tags=["blueprints"])

# Dependency for DB session — inject later
# async def get_db(): ...

@router.post("", response_model=BlueprintResponse, status_code=status.HTTP_201_CREATED)
async def create_blueprint(
    data: BlueprintCreate,
    session: AsyncSession = Depends(get_db),
):
    repo = BlueprintRepository(session)
    existing = await repo.get_by_slug(data.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Blueprint slug already exists")
    blueprint = AgentBlueprint(**data.model_dump())
    return await repo.create(blueprint)

@router.get("", response_model=list[BlueprintResponse])
async def list_blueprints(session: AsyncSession = Depends(get_db)):
    repo = BlueprintRepository(session)
    return await repo.list_all()

@router.get("/{id}", response_model=BlueprintResponse)
async def get_blueprint(id: UUID, session: AsyncSession = Depends(get_db)):
    repo = BlueprintRepository(session)
    bp = await repo.get_by_id(id)
    if not bp:
        raise HTTPException(status_code=404)
    return bp

@router.put("/{id}", response_model=BlueprintResponse)
async def update_blueprint(id: UUID, data: BlueprintCreate, session: AsyncSession = Depends(get_db)):
    repo = BlueprintRepository(session)
    bp = await repo.get_by_id(id)
    if not bp:
        raise HTTPException(status_code=404)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(bp, key, value)
    return await repo.update(bp)

@router.post("/{id}/activate")
async def activate_blueprint(id: UUID, session: AsyncSession = Depends(get_db)):
    repo = BlueprintRepository(session)
    bp = await repo.get_by_id(id)
    if not bp:
        raise HTTPException(status_code=404)
    bp.status = "active"
    await repo.update(bp)
    return {"status": "active"}

@router.post("/{id}/deactivate")
async def deactivate_blueprint(id: UUID, session: AsyncSession = Depends(get_db)):
    repo = BlueprintRepository(session)
    bp = await repo.get_by_id(id)
    if not bp:
        raise HTTPException(status_code=404)
    bp.status = "inactive"
    await repo.update(bp)
    return {"status": "inactive"}
```

**Test:** Integration test hitting the FastAPI TestClient.

Run: `pytest tests/integration/test_blueprint_api.py -v`
Expected: 6-7 PASS

---

### Task 1.6: AgentIdentity model + schema

**Objective:** Create the AgentIdentity SQLAlchemy model and Pydantic schemas.

**Files:**
- Create: `packages/identity_models/agent.py`
- Modify: `packages/identity_models/schemas.py` (add AgentCreate, AgentResponse)

**Model:**
```python
# packages/identity_models/agent.py
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from packages.common.models import Base, TimestampMixin, new_uuid
from packages.common.enums import AgentStatus


class AgentIdentity(Base, TimestampMixin):
    __tablename__ = "agent_identities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    principal_uri: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    blueprint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_blueprints.id"))
    owner_id: Mapped[str] = mapped_column(String(256))
    sponsor_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    status: Mapped[AgentStatus] = mapped_column(String(32), default=AgentStatus.DRAFT)
    public_key: Mapped[Optional[str]] = mapped_column(String(4096), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    blueprint = relationship("AgentBlueprint", lazy="selectin")
```

**Test:** Unit test for schema validation.

Run: `pytest tests/unit/test_agent_schemas.py -v`
Expected: 1-2 PASS

---

### Task 1.7: Agent identity repository + API endpoints

**Objective:** Full CRUD + lifecycle state machine for agents.

**Files:**
- Create: `apps/identity_api/repositories/agent_repo.py`
- Create: `apps/identity_api/api/agents.py`
- Modify: `apps/identity_api/main.py` (register agent router)

**API endpoints per spec:** POST, GET, GET/{id}, POST/{id}/activate, POST/{id}/suspend, POST/{id}/revoke, POST/{id}/rotate-key

**Lifecycle state machine rules:**
- Only ACTIVE agents can create sessions
- SUSPENDED and REVOKED are terminal until explicit state change
- DECOMMISSIONED is final (no state changes after)

**Test:** Integration tests for all lifecycle transitions.

Run: `pytest tests/integration/test_agent_api.py -v`
Expected: 8-10 PASS

---

### Task 1.8: Database migration + Alembic autogenerate

**Objective:** Generate initial migration, verify it runs.

**Steps:**
1. Run: `uv run alembic revision --autogenerate -m "initial_schema"`
2. Run: `uv run alembic upgrade head`
3. Verify tables exist: `uv run python -c "from sqlalchemy import inspect; ..."`

**Test:** Integration test that creates blueprint and agent via API, verifies DB state.

Run: `pytest tests/integration/test_migration.py -v`
Expected: 1-2 PASS

---

### Task 1.9: Sample blueprint YAML files

**Objective:** Create example blueprint files for demo scenarios.

**Files:**
- Create: `blueprints/research-agent.yaml`
- Create: `blueprints/support-agent.yaml`
- Create: `blueprints/deployment-agent.yaml`

**Content:** Per spec section 7.1.

---

### Task 1.10: Phase 1 final verification

**Steps:**
1. Run: `uv run ruff check apps/ packages/ tests/`
2. Run: `uv run ruff format --check apps/ packages/ tests/`
3. Run: `uv run pytest tests/ -v`
4. Run: `uv run alembic upgrade head && uv run pytest tests/integration/ -v`

Commit: `git add -A && git commit -m "feat: Phase 1 — Core Identity Model (blueprints + agents + lifecycle)"`

---

## Phase 2: Sessions and Tokens

**Deliver:** Runtime attestation model, signed JWT session tokens, delegation grants, token validation, session audit events.

### Task 2.1: RuntimeAttestation model + verification

**Objective:** Create attestation model with signature verification.

**Files:**
- Create: `packages/attestation/models.py`
- Create: `packages/attestation/verifier.py`

**Key logic:** Verify signature against registered agent public key, check timestamp freshness (5min window), validate nonce uniqueness.

### Task 2.2: DelegationGrant model + API

**Objective:** User-to-agent delegation records.

**Files:**
- Create: `packages/identity_models/delegation.py`
- Create: `apps/identity_api/api/delegations.py`

### Task 2.3: AgentSession model

**Objective:** Session model linking agent, user, delegation, attestation.

**Files:**
- Create: `packages/identity_models/session.py`

### Task 2.4: JWT token issuance and validation

**Objective:** Sign and verify Agent Session Tokens (asymmetric, RS256).

**Files:**
- Create: `packages/token_library/issuer.py`
- Create: `packages/token_library/validator.py`
- Create: `apps/identity_api/services/token_service.py`

**Claims per spec 12.1:** iss, sub, aud, iat, exp, jti, agent_id, blueprint_id, acting_user, delegation_id, scopes, runtime_digest, model, prompt_version, trace_id, policy_version.

**Validator checks:**
- Signature (asymmetric verify)
- Expiration
- Audience match
- Agent status via session lookup
- Algorithm (reject "none")

### Task 2.5: Session API endpoints

**Objective:** POST /v1/sessions, GET/{id}, POST/{id}/revoke.

**Files:**
- Create: `apps/identity_api/api/sessions.py`
- Create: `apps/identity_api/services/session_service.py`

**Session creation logic:**
1. Verify agent is ACTIVE
2. Verify blueprint is ACTIVE
3. Validate requested scopes ⊆ blueprint max_scopes
4. Verify runtime attestation (signature, freshness, nonce)
5. Check delegation grant (if user-delegated mode)
6. Create session record
7. Issue signed JWT
8. Write audit event

### Task 2.6: Session audit events

**Objective:** Write session.requested, session.approved, session.denied events.

**Files:**
- Create: `packages/audit/models.py`
- Create: `packages/audit/writer.py`

### Task 2.7: Phase 2 verification

Run full test suite + lint + type check. Commit.

---

## Phase 3: Policy Enforcement

**Deliver:** Policy adapter interface, OPA integration, scope intersection, allow/deny decisions.

### Task 3.1: Policy adapter interface

**Objective:** Abstract policy engine behind an adapter.

**Files:**
- Create: `packages/policy_client/adapter.py` (ABC)
- Create: `packages/policy_client/models.py` (PolicyInput, PolicyOutput)
- Create: `packages/policy_client/opa_adapter.py`

**PolicyInput:** agent, blueprint, user, session, runtime, tool, action, environment
**PolicyOutput:** decision, reason, effective_scopes, obligations, policy_version

### Task 3.2: OPA Rego policies

**Objective:** Write OPA policies for tool access.

**Files:**
- Create: `policies/agent_access.rego`
- Create: `policies/tool_access.rego`

**Key rules:** allow read operations, deny write operations for research agent, scope intersection, deny-by-default catch-all.

### Task 3.3: Scope intersection logic

**Objective:** Compute effective scopes = user ∩ agent ∩ blueprint ∩ tool ∩ env.

**Files:**
- Create: `apps/identity_api/services/policy_service.py`

**Test with Hypothesis:** Property `effective_scopes ⊆ requested_scopes` always.

### Task 3.4: Authorization API endpoint

**Objective:** POST /v1/authorize — validate session token, evaluate policy, return decision.

**Files:**
- Create: `apps/identity_api/api/authorization.py`

### Task 3.5: Phase 3 verification

Lint, type check, tests. Commit.

---

## Phase 4: MCP Gateway

**Deliver:** Gateway proxy, tool registry, tool-to-scope mappings, auth middleware, mock MCP server.

### Task 4.1: Tool registry + mappings

**Objective:** Define tool-to-scope mapping registry.

**Files:**
- Create: `apps/mcp_gateway/tool_registry/registry.py`
- Create: `apps/mcp_gateway/tool_registry/mappings.py`

**Example mapping:**
```python
TOOL_MAPPINGS = {
    "github.search_code": {"required_scopes": ["repo:read"]},
    "github.create_issue": {"required_scopes": ["issues:write"]},
}
```

### Task 4.2: Auth middleware

**Objective:** Validate session token on every request, extract claims, check authorization.

**Files:**
- Create: `apps/mcp_gateway/middleware/auth.py`
- Create: `apps/mcp_gateway/middleware/audit.py`

**Flow:**
1. Extract Bearer token
2. Validate JWT (signature, expiry, audience)
3. Verify agent status (call identity_api)
4. Look up tool mapping
5. Call authorize endpoint
6. If deny → 403
7. If allow → inject downstream creds, forward

### Task 4.3: Gateway proxy

**Objective:** Forward authorized requests to MCP server, inject credentials.

**Files:**
- Create: `apps/mcp_gateway/proxy/forwarder.py`
- Create: `apps/mcp_gateway/main.py`

### Task 4.4: Mock MCP server

**Objective:** Simple MCP server for testing.

**Files:**
- Create: `apps/mock_mcp_server/main.py`
- Create: `apps/mock_mcp_server/tools/github.py` (search_code, create_issue stubs)

### Task 4.5: Phase 4 verification

Integration test: agent → gateway → mock MCP server, verify auth flow.

---

## Phase 5: Token Brokerage

**Deliver:** Provider interface, mock OAuth provider, static secret injection, credential leases, secret redaction.

### Task 5.1: Credential provider interface

**Objective:** Abstract credential providers.

**Files:**
- Create: `apps/token_broker/providers/base.py` (ABC)
- Create: `apps/token_broker/providers/mock_oauth.py`
- Create: `apps/token_broker/providers/static_secret.py`

### Task 5.2: CredentialLease model

**Objective:** Track issued credentials without storing raw values.

**Files:**
- Create: `packages/identity_models/credential_lease.py`

### Task 5.3: Token exchange endpoint

**Objective:** POST /v1/token-exchange — callable only by MCP Gateway.

**Files:**
- Create: `apps/token_broker/main.py`
- Create: `apps/token_broker/services/exchange_service.py`

### Task 5.4: Secret redaction tests

**Objective:** Verify no raw secrets in logs, responses, or DB.

**Files:**
- Create: `tests/security/test_secret_redaction.py`

### Task 5.5: Phase 5 verification

Full integration: session → gateway → token broker → mock OAuth → gateway injects → mock MCP server.

---

## Phase 6: Audit and UI

**Deliver:** Tamper-evident audit chain, audit verification, admin dashboard, agent detail, session timeline.

### Task 6.1: Tamper-evident hash chain

**Objective:** Append-only hash chain: `record_hash = SHA256(previous_hash + canonical_event_json)`.

**Files:**
- Create: `packages/audit/chain.py`
- Modify: `packages/audit/writer.py` (hash chain integration)
- Modify: `packages/audit/models.py` (add previous_hash, record_hash)

### Task 6.2: Audit API endpoints

**Objective:** GET /v1/audit/events, GET/{id}, POST /v1/audit/verify-chain.

**Files:**
- Create: `apps/identity_api/api/audit.py`

### Task 6.3: Admin UI — Next.js scaffold

**Objective:** Next.js + TypeScript + Tailwind admin dashboard.

**Files:**
- Create: `apps/admin_ui/` (full Next.js project)
- Pages: Dashboard, Blueprints, Agents, Sessions, Audit Explorer

### Task 6.4: Dashboard page

**Objective:** Total identities, active/suspended, active sessions, denied actions, credentials issued, recent audit events.

### Task 6.5: Agent detail + lifecycle controls

**Objective:** Status, owner, blueprint, keys, recent sessions, revoke/suspend buttons.

### Task 6.6: Audit explorer

**Objective:** Filters by agent, user, tool, action, decision, session, date range, trace ID.

### Task 6.7: Phase 6 verification

Playwright E2E tests for UI. Lint, type check. Commit.

---

## Phase 7: Hermes Demo + Docs

**Deliver:** Python client SDK, Hermes integration example, typed execution-plan authorization, end-to-end demos, architecture documentation.

### Task 7.1: AgentIdentityClient SDK

**Objective:** Python client library for Hermes integration.

**Files:**
- Create: `packages/common/client.py`

**Interface per spec 17:**
```python
class AgentIdentityClient:
    async def create_session(agent_id, acting_user_id, requested_scopes, ...) -> AgentSession
    async def revoke_session(session_id)
    async def get_audit_events(...)
```

### Task 7.2: Hermes integration example

**Objective:** Example showing Hermes loading identity, creating attestation, obtaining session.

**Files:**
- Create: `examples/hermes_agent/run_with_identity.py`

### Task 7.3: Demo scenarios (6x)

**Objective:** One command per demo.

**Files:**
- Create: `examples/delegated_research/authorized_read.py`
- Create: `examples/unauthorized_write_attempt/denied_write.py`
- Create: `examples/hermes_agent/suspended_agent.py`
- Create: `examples/hermes_agent/invalid_runtime.py`
- Create: `examples/delegated_research/secret_isolation.py`
- Create: `examples/hermes_agent/user_lacks_permission.py`

### Task 7.4: Documentation

**Objective:** All docs deliverables per spec section 23.

**Files:**
- Create: `docs/architecture.md`
- Create: `docs/threat-model.md`
- Create: `docs/token-model.md`
- Create: `docs/policy-model.md`
- Create: `docs/mcp-integration.md`
- Create: `docs/hermes-integration.md`
- Create: `docs/demo.md`
- Create: `docs/adr/ADR-001-agents-as-principals.md`
- Create: `docs/adr/ADR-002-jwt-sessions.md`
- Create: `docs/adr/ADR-003-permission-intersection.md`
- Create: `docs/adr/ADR-004-server-side-injection.md`
- Create: `docs/adr/ADR-005-opa-adapter.md`
- Create: `docs/adr/ADR-006-audit-chain.md`
- Create: `docs/adr/ADR-007-gateway-boundary.md`

### Task 7.5: Final verification

- All tests pass
- Lint + type check pass
- `docker compose up` runs all services
- All 6 `make demo-*` pass
- Tag release: `git tag v0.1.0 && git push --tags`

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| OPA Rego policy language learning curve | Start with Python policy adapter as fallback (spec allows this) |
| Admin UI scope creep | Diagnostic-only UI; focus on API correctness first |
| Token key management complexity | Dev-only static keys; document rotation for production |
| Phase dependencies (can't parallelize across phases) | Within each phase, tasks can be parallelized via subagents |
| Codex quota exhaustion | Monitor quota; use subagents for smaller tasks |
| Testcontainers Docker availability | Fallback to SQLite for unit tests; PostgreSQL for integration via docker compose |

---

## Execution Plan

**Model:** deepseek-v4-pro for planning/architecture. Codex gpt-5.4 for implementation phases.

**Per phase:**
1. Update AGENTS.md with phase context
2. Dispatch Codex via worktree with full phase spec
3. Post-Codex: run lint fixup, type check, tests
4. Review + commit
5. Mark phase issue as done
6. Handoff document for next phase

**Parallel opportunities within phases:**
- Phase 1: Tasks 1.3-1.4 can run in parallel (model + repo are independent)
- Phase 3: Policy adapter + OPA policies can run in parallel
- Phase 6: Audit chain + UI scaffold can run in parallel
