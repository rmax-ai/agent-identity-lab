from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.identity_api.dependencies import get_db, require_admin
from packages.identity_models.delegation import DelegationGrant

router = APIRouter(prefix="/v1/delegations", tags=["delegations"])
db_session = Depends(get_db)
admin_key = Depends(require_admin)


class DelegationCreate(BaseModel):
    user_id: str
    agent_id: UUID
    scopes: list[str] = Field(default_factory=list)
    resource_constraints: dict = Field(default_factory=dict)
    ttl_seconds: int = Field(ge=1, le=86400, default=1800)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_delegation(
    data: DelegationCreate,
    session: AsyncSession = db_session,
    _admin: str = admin_key,
):
    now = datetime.now(UTC)
    delegation = DelegationGrant(
        user_id=data.user_id,
        agent_id=data.agent_id,
        scopes=data.scopes,
        resource_constraints=data.resource_constraints,
        issued_at=now,
        expires_at=now + timedelta(seconds=data.ttl_seconds),
    )
    session.add(delegation)
    await session.commit()
    await session.refresh(delegation)
    return {"id": str(delegation.id), "expires_at": delegation.expires_at.isoformat()}


@router.get("/{id}")
async def get_delegation(id: UUID, session: AsyncSession = db_session):
    delegation = await session.get(DelegationGrant, id)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    return {
        "id": str(delegation.id),
        "user_id": delegation.user_id,
        "agent_id": str(delegation.agent_id),
        "scopes": delegation.scopes,
        "issued_at": delegation.issued_at.isoformat(),
        "expires_at": delegation.expires_at.isoformat(),
        "revoked": delegation.revoked_at is not None,
    }


@router.post("/{id}/revoke")
async def revoke_delegation(
    id: UUID,
    session: AsyncSession = db_session,
    _admin: str = admin_key,
):
    delegation = await session.get(DelegationGrant, id)
    if not delegation:
        raise HTTPException(status_code=404, detail="Delegation not found")
    if delegation.revoked_at:
        raise HTTPException(status_code=400, detail="Delegation already revoked")
    delegation.revoked_at = datetime.now(UTC)
    await session.commit()
    return {"status": "revoked", "id": str(id)}
