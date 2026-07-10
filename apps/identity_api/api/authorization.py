"""Authorization endpoint for policy evaluation."""

from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.identity_api.dependencies import get_db, get_settings
from apps.identity_api.repositories.agent_repo import AgentRepository
from apps.identity_api.repositories.blueprint_repo import BlueprintRepository
from apps.identity_api.services.policy_service import PolicyService
from packages.attestation.models import RuntimeAttestation
from packages.common.settings import Settings
from packages.identity_models.session import AgentSession
from packages.policy_client.adapter import PolicyAdapter
from packages.policy_client.opa_adapter import OPAAdapter
from packages.policy_client.python_adapter import PythonPolicyAdapter
from packages.token_library.validator import validate_session_token

router = APIRouter(prefix="/v1", tags=["authorization"])
db_session = Depends(get_db)
settings_dependency = Depends(get_settings)


class AuthorizeRequest(BaseModel):
    session_token: str
    tool: str
    operation: str
    resource: dict = Field(default_factory=dict)


class AuthorizeResponse(BaseModel):
    decision: str
    effective_scopes: list[str]
    reason: str
    decision_id: str
    obligations: list[str]


async def get_policy_adapter(
    settings: Settings = settings_dependency,
) -> AsyncGenerator[PolicyAdapter, None]:
    """Try OPA first, then fall back to the Python adapter."""
    adapter = OPAAdapter(settings)
    if await adapter.health():
        try:
            yield adapter
        finally:
            await adapter.close()
        return

    await adapter.close()
    yield PythonPolicyAdapter()


policy_adapter_dependency = Depends(get_policy_adapter)


@router.post("/authorize", response_model=AuthorizeResponse)
async def authorize(
    data: AuthorizeRequest,
    db: AsyncSession = db_session,
    settings: Settings = settings_dependency,
    adapter: PolicyAdapter = policy_adapter_dependency,
):
    try:
        claims = validate_session_token(data.session_token, settings)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    session_id = claims.get("jti")
    session = await db.get(AgentSession, UUID(session_id)) if session_id else None
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found",
        )
    if session.revoked_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked",
        )

    agent = await AgentRepository(db).get_by_id(session.agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent not found",
        )

    blueprint = await BlueprintRepository(db).get_by_id(agent.blueprint_id)
    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Blueprint not found",
        )

    attestation = await db.get(RuntimeAttestation, session.runtime_attestation_id)
    runtime = {
        "environment": attestation.environment if attestation else "",
        "host_id": attestation.host_id if attestation else "",
        "framework": attestation.framework if attestation else "",
        "framework_version": attestation.framework_version if attestation else "",
        "model_id": attestation.model_id if attestation else session.model_id,
        "prompt_version": attestation.prompt_version if attestation else session.prompt_version,
    }

    result = await PolicyService(adapter).authorize_tool_access(
        agent={
            "id": str(agent.id),
            "status": str(agent.status),
            "scopes": session.effective_scopes,
        },
        blueprint={
            "id": str(blueprint.id),
            "slug": blueprint.slug,
            "status": str(blueprint.status),
            "max_scopes": blueprint.max_scopes,
            "approved_environments": blueprint.approved_environments,
            "approved_models": blueprint.approved_models,
        },
        user={
            "id": session.acting_user_id or "",
            "scopes": [],
        },
        session={
            "id": str(session.id),
            "model_id": session.model_id,
            "trace_id": session.trace_id,
        },
        runtime=runtime,
        tool_id=data.tool,
        operation=data.operation,
        requested_scopes=claims.get("scopes", []),
        environment=runtime["environment"] or "development",
    )

    return AuthorizeResponse(
        decision=result.decision,
        effective_scopes=result.effective_scopes,
        reason=result.reason,
        decision_id=f"dec_{session.trace_id}",
        obligations=result.obligations,
    )
