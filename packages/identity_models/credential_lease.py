import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from packages.common.models import Base, new_uuid

json_list_type = JSON().with_variant(JSONB(), "postgresql")
uuid_type = Uuid(as_uuid=True)


class CredentialLease(Base):
    __tablename__ = "credential_leases"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type, primary_key=True, default=new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type,
        ForeignKey("agent_sessions.id"),
        index=True,
    )
    tool_id: Mapped[str] = mapped_column(String(128))
    scopes: Mapped[list[str]] = mapped_column(json_list_type, default=list)
    provider: Mapped[str] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
