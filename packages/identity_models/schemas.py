from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from packages.common.enums import AgentStatus, BlueprintStatus


class BlueprintCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    approved_models: list[str] = Field(default_factory=list)
    approved_environments: list[str] = Field(default_factory=list)
    max_scopes: list[str] = Field(default_factory=list)
    tool_permissions: dict[str, list[str]] = Field(default_factory=dict)
    max_session_ttl_seconds: int = Field(ge=60, le=86400, default=1800)
    runtime_requirements: dict = Field(default_factory=dict)


class BlueprintUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    approved_models: list[str] | None = None
    approved_environments: list[str] | None = None
    max_scopes: list[str] | None = None
    tool_permissions: dict[str, list[str]] | None = None
    max_session_ttl_seconds: int | None = None
    runtime_requirements: dict | None = None


class BlueprintResponse(BaseModel):
    id: UUID
    slug: str
    version: int
    name: str
    description: str | None
    status: BlueprintStatus
    approved_models: list[str]
    approved_environments: list[str]
    max_scopes: list[str]
    tool_permissions: dict[str, list[str]]
    max_session_ttl_seconds: int
    runtime_requirements: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    blueprint_id: UUID
    owner_id: str = Field(min_length=1, max_length=256)
    sponsor_id: str | None = None
    public_key: str | None = None
    metadata: dict = Field(default_factory=dict)


class AgentResponse(BaseModel):
    id: UUID
    principal_uri: str
    blueprint_id: UUID
    owner_id: str
    sponsor_id: str | None
    status: AgentStatus
    public_key: str | None
    metadata: dict = Field(validation_alias="metadata_")
    created_at: datetime
    activated_at: datetime | None
    suspended_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class AgentKeyRotate(BaseModel):
    public_key: str
