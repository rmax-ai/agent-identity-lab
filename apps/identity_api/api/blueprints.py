from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.identity_api.dependencies import api_key_header, get_db, require_admin
from apps.identity_api.repositories.blueprint_repo import BlueprintRepository
from packages.common.enums import BlueprintStatus
from packages.identity_models.blueprint import AgentBlueprint
from packages.identity_models.schemas import (
    BlueprintCreate,
    BlueprintResponse,
    BlueprintUpdate,
)

router = APIRouter(prefix="/v1/blueprints", tags=["blueprints"])
db_session = Depends(get_db)
admin_key = Depends(require_admin)
api_key_security = Security(api_key_header)


def require_admin_header(api_key: str | None = api_key_security) -> str:
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")
    return api_key


admin_header = Depends(require_admin_header)


@router.post("", response_model=BlueprintResponse, status_code=status.HTTP_201_CREATED)
async def create_blueprint(
    data: BlueprintCreate,
    session: AsyncSession = db_session,
    _header: str = admin_header,
    _admin: str = admin_key,
):
    repo = BlueprintRepository(session)
    existing = await repo.get_by_slug(data.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Blueprint slug already exists")
    blueprint = AgentBlueprint(**data.model_dump())
    return await repo.create(blueprint)


@router.get("", response_model=list[BlueprintResponse])
async def list_blueprints(session: AsyncSession = db_session):
    repo = BlueprintRepository(session)
    return await repo.list_all()


@router.get("/{id}", response_model=BlueprintResponse)
async def get_blueprint(id: UUID, session: AsyncSession = db_session):
    repo = BlueprintRepository(session)
    blueprint = await repo.get_by_id(id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return blueprint


@router.put("/{id}", response_model=BlueprintResponse)
async def update_blueprint(
    id: UUID,
    data: BlueprintUpdate,
    session: AsyncSession = db_session,
    _header: str = admin_header,
    _admin: str = admin_key,
):
    repo = BlueprintRepository(session)
    blueprint = await repo.get_by_id(id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(blueprint, key, value)
    blueprint.version += 1
    return await repo.update(blueprint)


@router.post("/{id}/activate")
async def activate_blueprint(
    id: UUID,
    session: AsyncSession = db_session,
    _header: str = admin_header,
    _admin: str = admin_key,
):
    repo = BlueprintRepository(session)
    blueprint = await repo.get_by_id(id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    blueprint.status = BlueprintStatus.ACTIVE
    await repo.update(blueprint)
    return {"status": "active", "id": str(blueprint.id)}


@router.post("/{id}/deactivate")
async def deactivate_blueprint(
    id: UUID,
    session: AsyncSession = db_session,
    _header: str = admin_header,
    _admin: str = admin_key,
):
    repo = BlueprintRepository(session)
    blueprint = await repo.get_by_id(id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    blueprint.status = BlueprintStatus.INACTIVE
    await repo.update(blueprint)
    return {"status": "inactive", "id": str(blueprint.id)}
