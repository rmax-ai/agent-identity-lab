from enum import StrEnum


class BlueprintStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class AgentStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    DECOMMISSIONED = "decommissioned"


class VerificationResult(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class PolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class ExecutionMode(StrEnum):
    USER_DELEGATED = "user_delegated"
    MACHINE_ONLY = "machine_only"
