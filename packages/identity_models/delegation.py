import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from packages.common.models import Base, TimestampMixin, new_uuid

json_list_type = JSON().with_variant(JSONB(), "postgresql")
json_dict_type = JSON().with_variant(JSONB(), "postgresql")
uuid_type = Uuid(as_uuid=True)


class DelegationGrant(Base, TimestampMixin):
    __tablename__ = "delegation_grants"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type, primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(256), index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type,
        ForeignKey("agent_identities.id"),
    )
    scopes: Mapped[list[str]] = mapped_column(json_list_type, default=list)
    resource_constraints: Mapped[dict] = mapped_column(json_dict_type, default=dict)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
