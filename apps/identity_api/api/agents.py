from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.identity_api.dependencies import api_key_header, get_db, require_admin
from apps.identity_api.repositories.agent_repo import AgentRepository
from apps.identity_api.repositories.blueprint_repo import BlueprintRepository
from packages.common.enums import AgentStatus, BlueprintStatus
from packages.common.models import new_uuid
from packages.identity_models.agent import AgentIdentity
from packages.identity_models.schemas import AgentCreate, AgentKeyRotate, AgentResponse

router = APIRouter(prefix="/v1/agents", tags=["agents"])
db_session = Depends(get_db)
admin_key = Depends(require_admin)
api_key_security = Security(api_key_header)


def require_admin_header(api_key: str | None = api_key_security) -> str:
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")
    return api_key


admin_header = Depends(require_admin_header)


def build_principal_uri(agent_id: UUID, blueprint_slug: str) -> str:
    return f"agent://local/{blueprint_slug}/{agent_id}"


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    session: AsyncSession = db_session,
    _header: str = admin_header,
    _admin: str = admin_key,
):
    blueprint_repo = BlueprintRepository(session)
    blueprint = await blueprint_repo.get_by_id(data.blueprint_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    if blueprint.status != BlueprintStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Blueprint must be active")

    agent_id = new_uuid()
    agent = AgentIdentity(
        id=agent_id,
        principal_uri=build_principal_uri(agent_id, blueprint.slug),
        blueprint_id=data.blueprint_id,
        owner_id=data.owner_id,
        sponsor_id=data.sponsor_id,
        public_key=data.public_key,
        metadata_=data.metadata,
    )
    return await AgentRepository(session).create(agent)


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    blueprint_id: UUID | None = None,
    status: AgentStatus | None = None,
    session: AsyncSession = db_session,
):
    repo = AgentRepository(session)
    if blueprint_id:
        return await repo.list_by_blueprint(blueprint_id)
    if status:
        return await repo.list_by_status(status)
    return await repo.list_all()


@router.get("/{id}", response_model=AgentResponse)
async def get_agent(id: UUID, session: AsyncSession = db_session):
    repo = AgentRepository(session)
    agent = await repo.get_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{id}/activate")
async def activate_agent(
    id: UUID,
    session: AsyncSession = db_session,
    _header: str = admin_header,
    _admin: str = admin_key,
):
    repo = AgentRepository(session)
    agent = await repo.get_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status not in {
        AgentStatus.DRAFT,
        AgentStatus.PENDING_APPROVAL,
        AgentStatus.SUSPENDED,
    }:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot activate agent in status '{agent.status}'",
        )
    agent.status = AgentStatus.ACTIVE
    agent.activated_at = datetime.now(UTC)
    await repo.update(agent)
    return {"status": "active", "id": str(agent.id)}


@router.post("/{id}/suspend")
async def suspend_agent(
    id: UUID,
    session: AsyncSession = db_session,
    _header: str = admin_header,
    _admin: str = admin_key,
):
    repo = AgentRepository(session)
    agent = await repo.get_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != AgentStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot suspend agent in status '{agent.status}'",
        )
    agent.status = AgentStatus.SUSPENDED
    agent.suspended_at = datetime.now(UTC)
    await repo.update(agent)
    return {"status": "suspended", "id": str(agent.id)}


@router.post("/{id}/revoke")
async def revoke_agent(
    id: UUID,
    session: AsyncSession = db_session,
    _header: str = admin_header,
    _admin: str = admin_key,
):
    repo = AgentRepository(session)
    agent = await repo.get_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status = AgentStatus.REVOKED
    agent.revoked_at = datetime.now(UTC)
    await repo.update(agent)
    return {"status": "revoked", "id": str(agent.id)}


@router.post("/{id}/rotate-key")
async def rotate_key(
    id: UUID,
    data: AgentKeyRotate,
    session: AsyncSession = db_session,
    _header: str = admin_header,
    _admin: str = admin_key,
):
    repo = AgentRepository(session)
    agent = await repo.get_by_id(id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.public_key = data.public_key
    await repo.update(agent)
    return {"status": "key_rotated", "id": str(agent.id)}
