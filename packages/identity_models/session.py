import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from packages.common.models import Base, TimestampMixin, new_uuid

json_list_type = JSON().with_variant(JSONB(), "postgresql")
uuid_type = Uuid(as_uuid=True)


class AgentSession(Base, TimestampMixin):
    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type, primary_key=True, default=new_uuid)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type,
        ForeignKey("agent_identities.id"),
        index=True,
    )
    acting_user_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    delegation_grant_id: Mapped[uuid.UUID | None] = mapped_column(
        uuid_type,
        ForeignKey("delegation_grants.id"),
        nullable=True,
    )
    model_id: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(64))
    runtime_attestation_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type,
        ForeignKey("runtime_attestations.id"),
    )
    requested_scopes: Mapped[list[str]] = mapped_column(json_list_type, default=list)
    effective_scopes: Mapped[list[str]] = mapped_column(json_list_type, default=list)
    policy_version: Mapped[str] = mapped_column(String(64), default="0.0.0")
    trace_id: Mapped[str] = mapped_column(String(128), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
