# Phase 1: Core Identity Model

You are implementing Phase 1 of the Agent Identity Lab — an open-source identity and authorization control plane for AI agents.

**Context:** The project is already scaffolded with:
- `packages/common/settings.py` — pydantic-settings for env vars
- `apps/identity_api/dependencies.py` — `get_db` (async session), `require_admin` (API key middleware)
- `apps/identity_api/main.py` — FastAPI app with CORS, JSON logging, `/health` endpoint
- `tests/conftest.py` — FastAPI TestClient + SQLite fixtures
- `SPEC.md` — full 24-section specification (read section 11 for domain models, section 13 for API endpoints)

**Tech stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), PostgreSQL (via asyncpg), Alembic

**Test command:** `PYTHONPATH=. uv run pytest tests/ -v`
**Lint command:** `PYTHONPATH=. uv run ruff check packages/ apps/ tests/`
**Format command:** `PYTHONPATH=. uv run ruff format packages/ apps/ tests/`

## Files to Create

### 1. packages/common/enums.py
```python
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

### 2. packages/common/models.py
Overwrite the existing `__init__.py` content with:
```python
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

### 3. packages/identity_models/blueprint.py
```python
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

### 4. packages/identity_models/agent.py
```python
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

### 5. packages/identity_models/schemas.py
```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from packages.common.enums import BlueprintStatus, AgentStatus


# --- Blueprint Schemas ---

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


class BlueprintUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    approved_models: list[str] | None = None
    approved_environments: list[str] | None = None
    max_scopes: list[str] | None = None
    tool_permissions: dict[str, list[str]] | None = None
    max_session_ttl_seconds: int | None = None
    runtime_requirements: dict | None = None


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


# --- Agent Schemas ---

class AgentCreate(BaseModel):
    blueprint_id: UUID
    owner_id: str = Field(min_length=1, max_length=256)
    sponsor_id: str | None = None
    public_key: str | None = None
    metadata: dict = Field(default_factory=dict)


class AgentResponse(BaseModel):
    id: UUID
    principal_uri: str
    blueprint_id: UUID
    owner_id: str
    sponsor_id: str | None
    status: AgentStatus
    public_key: str | None
    metadata: dict
    created_at: datetime
    activated_at: datetime | None
    suspended_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class AgentKeyRotate(BaseModel):
    public_key: str
```

### 6. apps/identity_api/repositories/blueprint_repo.py
```python
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

    async def get_by_id(self, id_: UUID) -> AgentBlueprint | None:
        return await self.session.get(AgentBlueprint, id_)

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

### 7. apps/identity_api/repositories/agent_repo.py
```python
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.identity_models.agent import AgentIdentity
from packages.common.enums import AgentStatus


class AgentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, agent: AgentIdentity) -> AgentIdentity:
        self.session.add(agent)
        await self.session.commit()
        await self.session.refresh(agent)
        return agent

    async def get_by_id(self, id_: UUID) -> AgentIdentity | None:
        return await self.session.get(AgentIdentity, id_)

    async def list_all(self) -> list[AgentIdentity]:
        result = await self.session.execute(select(AgentIdentity))
        return list(result.scalars().all())

    async def list_by_blueprint(self, blueprint_id: UUID) -> list[AgentIdentity]:
        result = await self.session.execute(
            select(AgentIdentity).where(AgentIdentity.blueprint_id == blueprint_id)
        )
        return list(result.scalars().all())

    async def list_by_status(self, status: AgentStatus) -> list[AgentIdentity]:
        result = await self.session.execute(
            select(AgentIdentity).where(AgentIdentity.status == status)
        )
        return list(result.scalars().all())

    async def update(self, agent: AgentIdentity) -> AgentIdentity:
        await self.session.commit()
        await self.session.refresh(agent)
        return agent
```

### 8. apps/identity_api/api/blueprints.py
```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from packages.identity_models.schemas import BlueprintCreate, BlueprintUpdate, BlueprintResponse
from packages.identity_models.blueprint import AgentBlueprint
from packages.common.enums import BlueprintStatus
from apps.identity_api.repositories.blueprint_repo import BlueprintRepository
from apps.identity_api.dependencies import get_db, require_admin

router = APIRouter(prefix="/v1/blueprints", tags=["blueprints"])


@router.post("", response_model=BlueprintResponse, status_code=status.HTTP_201_CREATED)
async def create_blueprint(
    data: BlueprintCreate,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
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
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return bp


@router.put("/{id}", response_model=BlueprintResponse)
async def update_blueprint(
    id: UUID,
    data: BlueprintUpdate,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    repo = BlueprintRepository(session)
    bp = await repo.get_by_id(id)
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(bp, key, value)
    bp.version += 1
    return await repo.update(bp)


@router.post("/{id}/activate")
async def activate_blueprint(
    id: UUID,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    repo = BlueprintRepository(session)
    bp = await repo.get_by_id(id)
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    bp.status = BlueprintStatus.ACTIVE
    await repo.update(bp)
    return {"status": "active", "id": str(bp.id)}


@router.post("/{id}/deactivate")
async def deactivate_blueprint(
    id: UUID,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    repo = BlueprintRepository(session)
    bp = await repo.get_by_id(id)
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    bp.status = BlueprintStatus.INACTIVE
    await repo.update(bp)
    return {"status": "inactive", "id": str(bp.id)}
```

### 9. apps/identity_api/api/agents.py
```python
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from packages.identity_models.schemas import AgentCreate, AgentResponse, AgentKeyRotate
from packages.identity_models.agent import AgentIdentity
from packages.identity_models.blueprint import AgentBlueprint
from packages.common.enums import AgentStatus
from apps.identity_api.repositories.agent_repo import AgentRepository
from apps.identity_api.repositories.blueprint_repo import BlueprintRepository
from apps.identity_api.dependencies import get_db, require_admin

router = APIRouter(prefix="/v1/agents", tags=["agents"])


def build_principal_uri(agent_id: UUID, blueprint_slug: str) -> str:
    return f"agent://local/{blueprint_slug}/{agent_id}"


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    bp_repo = BlueprintRepository(session)
    blueprint = await bp_repo.get_by_id(data.blueprint_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    if blueprint.status != "active":
        raise HTTPException(status_code=400, detail="Blueprint must be active")

    agent_repo = AgentRepository(session)
    agent = AgentIdentity(
        blueprint_id=data.blueprint_id,
        owner_id=data.owner_id,
        sponsor_id=data.sponsor_id,
        public_key=data.public_key,
        metadata_=data.metadata or {},
    )
    agent = await agent_repo.create(agent)
    agent.principal_uri = build_principal_uri(agent.id, blueprint.slug)
    await agent_repo.update(agent)
    return agent


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    blueprint_id: UUID | None = None,
    status: AgentStatus | None = None,
    session: AsyncSession = Depends(get_db),
):
    repo = AgentRepository(session)
    if blueprint_id:
        return await repo.list_by_blueprint(blueprint_id)
    if status:
        return await repo.list_by_status(status)
    return await repo.list_all()


@router.get("/{id}", response_model=AgentResponse)
async def get_agent(id: UUID, session: AsyncSession = Depends(get_db)):
    repo = AgentRepository(session)
    agent = await repo.get_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{id}/activate")
async def activate_agent(
    id: UUID,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    repo = AgentRepository(session)
    agent = await repo.get_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status not in (AgentStatus.DRAFT, AgentStatus.PENDING_APPROVAL, AgentStatus.SUSPENDED):
        raise HTTPException(status_code=400, detail=f"Cannot activate agent in status '{agent.status}'")
    agent.status = AgentStatus.ACTIVE
    agent.activated_at = datetime.now(timezone.utc)
    await repo.update(agent)
    return {"status": "active", "id": str(agent.id)}


@router.post("/{id}/suspend")
async def suspend_agent(
    id: UUID,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    repo = AgentRepository(session)
    agent = await repo.get_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != AgentStatus.ACTIVE:
        raise HTTPException(status_code=400, detail=f"Cannot suspend agent in status '{agent.status}'")
    agent.status = AgentStatus.SUSPENDED
    agent.suspended_at = datetime.now(timezone.utc)
    await repo.update(agent)
    return {"status": "suspended", "id": str(agent.id)}


@router.post("/{id}/revoke")
async def revoke_agent(
    id: UUID,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    repo = AgentRepository(session)
    agent = await repo.get_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status = AgentStatus.REVOKED
    agent.revoked_at = datetime.now(timezone.utc)
    await repo.update(agent)
    return {"status": "revoked", "id": str(agent.id)}


@router.post("/{id}/rotate-key")
async def rotate_key(
    id: UUID,
    data: AgentKeyRotate,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    repo = AgentRepository(session)
    agent = await repo.get_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.public_key = data.public_key
    await repo.update(agent)
    return {"status": "key_rotated", "id": str(agent.id)}
```

### 10. apps/identity_api/main.py — register routers

In `apps/identity_api/main.py`, add these imports and router registrations at the bottom (after the existing code):

```python
from apps.identity_api.api import blueprints, agents

app.include_router(blueprints.router)
app.include_router(agents.router)
```

### 11. blueprints/research-agent.yaml
```yaml
id: research-agent
version: 1
name: Research Agent
description: Read-only technical research agent
status: active

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

### 12. blueprints/support-agent.yaml
```yaml
id: support-agent
version: 1
name: Support Agent
description: Customer support agent with issue tracking access
status: active

approved_models:
  - openai:gpt-5-mini
  - deepseek:deepseek-chat

approved_environments:
  - development
  - staging

tools:
  - id: github
    scopes:
      - issues:read
      - issues:write
  - id: confluence
    scopes:
      - pages:read

session:
  max_ttl_seconds: 3600

runtime:
  require_container_digest: true
  require_git_commit: true
  require_signed_attestation: false
```

### 13. blueprints/deployment-agent.yaml
```yaml
id: deployment-agent
version: 1
name: Deployment Agent
description: CI/CD deployment agent
status: active

approved_models:
  - openai:gpt-5-mini

approved_environments:
  - staging
  - production

tools:
  - id: github
    scopes:
      - repo:read
      - repo:write
      - actions:write
      - deployments:write

session:
  max_ttl_seconds: 900

runtime:
  require_container_digest: true
  require_git_commit: true
  require_signed_attestation: true
```

### 14. Tests — tests/unit/test_enums.py
```python
from packages.common.enums import AgentStatus, BlueprintStatus, PolicyDecision


class TestAgentStatus:
    def test_active_value(self):
        assert AgentStatus.ACTIVE.value == "active"

    def test_suspended_value(self):
        assert AgentStatus.SUSPENDED.value == "suspended"

    def test_revoked_terminal(self):
        assert AgentStatus.REVOKED.value == "revoked"
        assert AgentStatus.DECOMMISSIONED.value == "decommissioned"


class TestBlueprintStatus:
    def test_draft_default(self):
        assert BlueprintStatus.DRAFT.value == "draft"

    def test_active_deprecated(self):
        assert BlueprintStatus.ACTIVE.value == "active"
        assert BlueprintStatus.DEPRECATED.value == "deprecated"


class TestPolicyDecision:
    def test_decisions(self):
        assert PolicyDecision.ALLOW.value == "allow"
        assert PolicyDecision.DENY.value == "deny"
```

### 15. Tests — tests/unit/test_blueprint_schemas.py
```python
from packages.identity_models.schemas import BlueprintCreate


class TestBlueprintCreate:
    def test_defaults(self):
        bp = BlueprintCreate(slug="test-bp", name="Test Blueprint")
        assert bp.slug == "test-bp"
        assert bp.approved_models == []
        assert bp.max_session_ttl_seconds == 1800

    def test_min_ttl_enforced(self):
        bp = BlueprintCreate(slug="t", name="T", max_session_ttl_seconds=60)
        assert bp.max_session_ttl_seconds == 60

    def test_slug_validation(self):
        bp = BlueprintCreate(slug="valid-slug-123", name="Valid")
        assert bp.slug == "valid-slug-123"
```

### 16. Tests — tests/integration/test_blueprint_api.py
```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_blueprint(client: AsyncClient):
    response = await client.post(
        "/v1/blueprints",
        json={"slug": "test-bp", "name": "Test Blueprint"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "test-bp"
    assert data["status"] == "draft"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_blueprints(client: AsyncClient):
    # Create one first
    await client.post(
        "/v1/blueprints",
        json={"slug": "list-test", "name": "List Test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    response = await client.get("/v1/blueprints")
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_get_blueprint_not_found(client: AsyncClient):
    response = await client.get("/v1/blueprints/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_activate_blueprint(client: AsyncClient):
    # Create
    r = await client.post(
        "/v1/blueprints",
        json={"slug": "activate-test", "name": "Activate Test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = r.json()["id"]

    # Activate
    r2 = await client.post(
        f"/v1/blueprints/{bp_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert r2.status_code == 200

    # Verify
    r3 = await client.get(f"/v1/blueprints/{bp_id}")
    assert r3.json()["status"] == "active"


@pytest.mark.asyncio
async def test_create_duplicate_slug(client: AsyncClient):
    await client.post(
        "/v1/blueprints",
        json={"slug": "dup-test", "name": "First"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    r = await client.post(
        "/v1/blueprints",
        json={"slug": "dup-test", "name": "Second"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_requires_admin_key(client: AsyncClient):
    r = await client.post(
        "/v1/blueprints",
        json={"slug": "no-auth", "name": "No Auth"},
    )
    assert r.status_code == 401
```

### 17. Tests — tests/integration/test_agent_api.py
```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_agent(client: AsyncClient):
    # First create an active blueprint
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "agent-bp", "name": "Agent BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(
        f"/v1/blueprints/{bp_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    # Create agent
    r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["owner_id"] == "usr_test"
    assert data["status"] == "draft"
    assert data["principal_uri"].startswith("agent://local/")


@pytest.mark.asyncio
async def test_activate_agent(client: AsyncClient):
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "act-agent-bp", "name": "Act Agent BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(
        f"/v1/blueprints/{bp_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]

    r = await client.post(
        f"/v1/agents/{agent_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert r.status_code == 200

    r2 = await client.get(f"/v1/agents/{agent_id}")
    assert r2.json()["status"] == "active"
    assert r2.json()["activated_at"] is not None


@pytest.mark.asyncio
async def test_suspend_agent(client: AsyncClient):
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "susp-bp", "name": "Suspension BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(f"/v1/blueprints/{bp_id}/activate", headers={"X-Admin-API-Key": "test-admin-key"})

    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]
    await client.post(f"/v1/agents/{agent_id}/activate", headers={"X-Admin-API-Key": "test-admin-key"})

    r = await client.post(f"/v1/agents/{agent_id}/suspend", headers={"X-Admin-API-Key": "test-admin-key"})
    assert r.status_code == 200

    r2 = await client.get(f"/v1/agents/{agent_id}")
    assert r2.json()["status"] == "suspended"


@pytest.mark.asyncio
async def test_revoke_agent(client: AsyncClient):
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "revoke-bp", "name": "Revoke BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(f"/v1/blueprints/{bp_id}/activate", headers={"X-Admin-API-Key": "test-admin-key"})

    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]

    r = await client.post(f"/v1/agents/{agent_id}/revoke", headers={"X-Admin-API-Key": "test-admin-key"})
    assert r.status_code == 200
    assert r.json()["status"] == "revoked"
```

## What NOT to modify
- packages/common/settings.py
- apps/identity_api/dependencies.py
- apps/identity_api/main.py (except adding router registrations at the bottom)
- tests/conftest.py
- pyproject.toml
- docker-compose.yml
- Any file under docs/, examples/, policies/, apps/token_broker/, apps/mcp_gateway/, apps/mock_mcp_server/

## Verification
After writing all files, run:
```
PYTHONPATH=. uv run pytest tests/ -v
```

Expected: All tests pass. If any fail, fix the implementation (not the tests).

Then run:
```
PYTHONPATH=. uv run ruff check packages/ apps/ tests/
PYTHONPATH=. uv run ruff format packages/ apps/ tests/
```

Fix any lint issues. Format the code. Verify tests still pass.
