import uuid

from sqlalchemy import Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from packages.common.enums import BlueprintStatus
from packages.common.models import Base, TimestampMixin, new_uuid

json_list_type = JSON().with_variant(JSONB(), "postgresql")
json_dict_type = JSON().with_variant(JSONB(), "postgresql")
uuid_type = Uuid(as_uuid=True)


class AgentBlueprint(Base, TimestampMixin):
    __tablename__ = "agent_blueprints"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type, primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[BlueprintStatus] = mapped_column(String(32), default=BlueprintStatus.DRAFT)
    approved_models: Mapped[list[str]] = mapped_column(json_list_type, default=list)
    approved_environments: Mapped[list[str]] = mapped_column(json_list_type, default=list)
    max_scopes: Mapped[list[str]] = mapped_column(json_list_type, default=list)
    tool_permissions: Mapped[dict[str, list[str]]] = mapped_column(json_dict_type, default=dict)
    max_session_ttl_seconds: Mapped[int] = mapped_column(Integer, default=1800)
    runtime_requirements: Mapped[dict] = mapped_column(json_dict_type, default=dict)
