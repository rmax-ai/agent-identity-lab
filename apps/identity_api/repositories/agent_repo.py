from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.enums import AgentStatus
from packages.identity_models.agent import AgentIdentity


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
