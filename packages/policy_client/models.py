"""Policy evaluation models."""

from pydantic import BaseModel, Field


class PolicyInput(BaseModel):
    agent: dict = Field(default_factory=dict)
    blueprint: dict = Field(default_factory=dict)
    user: dict = Field(default_factory=dict)
    session: dict = Field(default_factory=dict)
    runtime: dict = Field(default_factory=dict)
    tool: dict = Field(default_factory=dict)
    action: dict = Field(default_factory=dict)
    environment: dict = Field(default_factory=dict)


class PolicyOutput(BaseModel):
    decision: str
    reason: str = ""
    effective_scopes: list[str] = Field(default_factory=list)
    obligations: list[str] = Field(default_factory=list)
    policy_version: str = "0.0.0"
