from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.identity_api.dependencies import get_db, get_settings
from apps.identity_api.services.session_service import SessionError, SessionService
from packages.common.settings import Settings
from packages.identity_models.session import AgentSession

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])
db_session = Depends(get_db)
settings_dependency = Depends(get_settings)


class SessionCreateRequest(BaseModel):
    agent_id: UUID
    acting_user_id: str | None = None
    delegation_grant_id: UUID | None = None
    requested_scopes: list[str] = Field(default_factory=list)
    requested_ttl_seconds: int = Field(ge=1, le=1800, default=900)
    model_id: str
    prompt_version: str = "v1"
    runtime_attestation: dict = Field(default_factory=dict)


class SessionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    acting_user_id: str | None
    token: str
    trace_id: str
    effective_scopes: list[str]
    issued_at: str
    expires_at: str

    model_config = {"from_attributes": True}


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreateRequest,
    db: AsyncSession = db_session,
    settings: Settings = settings_dependency,
):
    service = SessionService(db, settings)
    attestation_data = dict(data.runtime_attestation)
    signature = attestation_data.pop("signature", "")

    try:
        session, token = await service.create_session(
            agent_id=data.agent_id,
            acting_user_id=data.acting_user_id,
            delegation_grant_id=data.delegation_grant_id,
            requested_scopes=data.requested_scopes,
            requested_ttl_seconds=data.requested_ttl_seconds,
            model_id=data.model_id,
            prompt_version=data.prompt_version,
            attestation_data=attestation_data,
            attestation_signature=signature,
        )
    except SessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SessionResponse(
        id=session.id,
        agent_id=session.agent_id,
        acting_user_id=session.acting_user_id,
        token=token,
        trace_id=session.trace_id,
        effective_scopes=session.effective_scopes,
        issued_at=session.issued_at.isoformat(),
        expires_at=session.expires_at.isoformat(),
    )


@router.get("/{id}")
async def get_session(
    id: UUID,
    db: AsyncSession = db_session,
):
    session = await db.get(AgentSession, id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": str(session.id),
        "agent_id": str(session.agent_id),
        "acting_user_id": session.acting_user_id,
        "status": "revoked" if session.revoked_at else "active",
        "effective_scopes": session.effective_scopes,
        "trace_id": session.trace_id,
        "issued_at": session.issued_at.isoformat(),
        "expires_at": session.expires_at.isoformat(),
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
    }


@router.post("/{id}/revoke")
async def revoke_session(
    id: UUID,
    db: AsyncSession = db_session,
    settings: Settings = settings_dependency,
):
    service = SessionService(db, settings)
    try:
        await service.revoke_session(id)
        return {"status": "revoked", "id": str(id)}
    except SessionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
