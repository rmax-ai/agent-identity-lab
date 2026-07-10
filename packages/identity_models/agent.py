import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from packages.common.enums import AgentStatus
from packages.common.models import Base, TimestampMixin, new_uuid

json_dict_type = JSON().with_variant(JSONB(), "postgresql")
uuid_type = Uuid(as_uuid=True)


class AgentIdentity(Base, TimestampMixin):
    __tablename__ = "agent_identities"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type, primary_key=True, default=new_uuid)
    principal_uri: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type,
        ForeignKey("agent_blueprints.id"),
    )
    owner_id: Mapped[str] = mapped_column(String(256))
    sponsor_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[AgentStatus] = mapped_column(String(32), default=AgentStatus.DRAFT)
    public_key: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", json_dict_type, default=dict)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    blueprint = relationship("AgentBlueprint", lazy="selectin")
