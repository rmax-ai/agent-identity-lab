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
