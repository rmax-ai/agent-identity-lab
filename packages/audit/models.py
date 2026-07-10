import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.common.models import Base, new_uuid

json_dict_type = JSON().with_variant(JSONB(), "postgresql")
uuid_type = Uuid(as_uuid=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type, primary_key=True, default=new_uuid)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(uuid_type, nullable=True)
    acting_user_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(uuid_type, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    tool_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    operation: Mapped[str | None] = mapped_column(String(256), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(json_dict_type, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    record_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
