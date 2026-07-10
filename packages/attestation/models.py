import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from packages.common.enums import VerificationResult
from packages.common.models import Base, TimestampMixin, new_uuid

uuid_type = Uuid(as_uuid=True)


class RuntimeAttestation(Base, TimestampMixin):
    __tablename__ = "runtime_attestations"

    id: Mapped[uuid.UUID] = mapped_column(uuid_type, primary_key=True, default=new_uuid)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        uuid_type,
        ForeignKey("agent_identities.id"),
        index=True,
    )
    container_digest: Mapped[str] = mapped_column(String(256))
    git_commit: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(64))
    host_id: Mapped[str] = mapped_column(String(256))
    framework: Mapped[str] = mapped_column(String(64))
    framework_version: Mapped[str] = mapped_column(String(32))
    model_id: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[str] = mapped_column(String(128), unique=True)
    signature: Mapped[str] = mapped_column(String(4096))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_result: Mapped[VerificationResult | None] = mapped_column(
        String(32),
        nullable=True,
    )
