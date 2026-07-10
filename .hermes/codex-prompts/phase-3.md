# Phase 3: Policy Enforcement

Implementing policy adapter interface, OPA integration, scope intersection, and the /v1/authorize endpoint.

**Context:** Phases 1-2 are complete. The codebase has working:
- Blueprint + Agent CRUD (Phase 1)
- Session creation with JWT tokens + attestation verification (Phase 2)
- 36 passing tests

**Read before starting:**
- `SPEC.md` section 7.6 (Policy Evaluation), 14 (Policy Examples)
- `packages/common/settings.py` — OPA_URL setting
- `packages/token_library/validator.py` — token validation
- `apps/identity_api/services/session_service.py` — session creation

**Test:** `PYTHONPATH=. uv run pytest tests/ -v`
**Lint:** `PYTHONPATH=. uv run ruff check packages/ apps/ tests/`

## Files to Create

### 1. packages/policy_client/models.py
```python
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
    decision: str  # "allow" or "deny"
    reason: str = ""
    effective_scopes: list[str] = Field(default_factory=list)
    obligations: list[str] = Field(default_factory=list)
    policy_version: str = "0.0.0"
```

### 2. packages/policy_client/adapter.py
```python
"""Abstract policy engine adapter."""

from abc import ABC, abstractmethod
from packages.policy_client.models import PolicyInput, PolicyOutput


class PolicyAdapter(ABC):
    """Abstract interface for policy engines (OPA, Cedar, Python, etc.)."""

    @abstractmethod
    async def evaluate(self, policy_input: PolicyInput) -> PolicyOutput:
        """Evaluate a policy decision for the given input."""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Check if the policy engine is reachable."""
        ...


class PolicyError(Exception):
    """Policy evaluation error."""
    pass
```

### 3. packages/policy_client/python_adapter.py
```python
"""Python-native policy adapter (fallback when OPA is unavailable)."""

from packages.policy_client.adapter import PolicyAdapter, PolicyError
from packages.policy_client.models import PolicyInput, PolicyOutput


class PythonPolicyAdapter(PolicyAdapter):
    """Simple Python-based policy evaluator.

    Implements scope intersection: effective = agent ∩ blueprint ∩ tool ∩ requested.
    Deny-by-default for unknown tools.
    Research agents denied write scopes.
    """

    TOOL_SCOPE_MAP = {
        "github.search_code": {"required_scopes": ["repo:read"]},
        "github.create_issue": {"required_scopes": ["issues:write"]},
        "github.list_repos": {"required_scopes": ["repo:read"]},
        "confluence.search": {"required_scopes": ["pages:read"]},
        "confluence.create_page": {"required_scopes": ["pages:write"]},
    }

    async def evaluate(self, policy_input: PolicyInput) -> PolicyOutput:
        agent = policy_input.agent
        blueprint = policy_input.blueprint
        user = policy_input.user
        tool = policy_input.tool
        action = policy_input.action
        runtime = policy_input.runtime

        # 1. Agent must be active
        if agent.get("status") != "active":
            return PolicyOutput(
                decision="deny",
                reason="Agent is not active",
                policy_version="python-1.0",
            )

        # 2. Blueprint must be active
        if blueprint.get("status") != "active":
            return PolicyOutput(
                decision="deny",
                reason="Blueprint is not active",
                policy_version="python-1.0",
            )

        # 3. Tool must be registered (deny-by-default)
        tool_id = tool.get("id", "")
        operation = action.get("operation", "")
        tool_key = f"{tool_id}.{operation}" if tool_id and operation else tool_id
        required = self.TOOL_SCOPE_MAP.get(tool_key)
        if required is None:
            return PolicyOutput(
                decision="deny",
                reason=f"Unknown tool or operation: {tool_key}",
                policy_version="python-1.0",
            )

        # 4. Research agents cannot have write scopes
        if blueprint.get("slug") == "research-agent":
            if any(s.endswith(":write") for s in required["required_scopes"]):
                return PolicyOutput(
                    decision="deny",
                    reason="Research agents cannot perform write operations",
                    policy_version="python-1.0",
                )

        # 5. Environment check
        approved_envs = blueprint.get("approved_environments", [])
        env = runtime.get("environment", "")
        if approved_envs and env not in approved_envs:
            return PolicyOutput(
                decision="deny",
                reason=f"Environment '{env}' not in approved environments",
                policy_version="python-1.0",
            )

        # 6. Scope intersection
        agent_scopes = set(agent.get("scopes", []))
        blueprint_scopes = set(blueprint.get("max_scopes", []))
        user_scopes = set(user.get("scopes", []))
        tool_required = set(required["required_scopes"])
        requested = set(action.get("requested_scopes", tool_required))

        # Start with all requested scopes, intersect down
        effective = requested & agent_scopes & blueprint_scopes & tool_required
        if user_scopes:
            effective = effective & user_scopes

        if not effective:
            removed = requested - effective
            return PolicyOutput(
                decision="deny",
                reason=f"No scopes remain after intersection. Removed: {removed}",
                effective_scopes=list(effective),
                policy_version="python-1.0",
            )

        # 7. Allow with effective scopes
        return PolicyOutput(
            decision="allow",
            reason="Permission intersection satisfied",
            effective_scopes=list(effective),
            obligations=["log_request"],
            policy_version="python-1.0",
        )

    async def health(self) -> bool:
        return True
```

### 4. packages/policy_client/opa_adapter.py
```python
"""OPA policy adapter using the OPA REST API."""

import httpx
from packages.policy_client.adapter import PolicyAdapter, PolicyError
from packages.policy_client.models import PolicyInput, PolicyOutput
from packages.common.settings import Settings


class OPAAdapter(PolicyAdapter):
    """Policy adapter that delegates to Open Policy Agent via REST API."""

    def __init__(self, settings: Settings):
        self.base_url = settings.opa_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=10.0)

    async def evaluate(self, policy_input: PolicyInput) -> PolicyOutput:
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/data/agent_identity/tool_access",
                json={"input": policy_input.model_dump()},
            )
            response.raise_for_status()
            result = response.json().get("result", {})

            if result.get("allow"):
                return PolicyOutput(
                    decision="allow",
                    reason=result.get("reason", "Policy allowed"),
                    effective_scopes=result.get("effective_scopes", []),
                    obligations=result.get("obligations", []),
                    policy_version=result.get("policy_version", "opa-0.0.0"),
                )
            else:
                return PolicyOutput(
                    decision="deny",
                    reason=result.get("deny_reason", result.get("reason", "Policy denied")),
                    policy_version=result.get("policy_version", "opa-0.0.0"),
                )
        except httpx.HTTPError as e:
            # OPA unavailable — fail-closed
            return PolicyOutput(
                decision="deny",
                reason=f"Policy service unavailable: {e}",
                policy_version="opa-unavailable",
            )

    async def health(self) -> bool:
        try:
            r = await self.client.get(f"{self.base_url}/health")
            return r.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.client.aclose()
```

### 5. apps/identity_api/services/policy_service.py
```python
"""Policy evaluation service with scope intersection."""

import uuid
from packages.policy_client.adapter import PolicyAdapter
from packages.policy_client.models import PolicyInput, PolicyOutput


class PolicyService:
    """Orchestrates policy evaluation for agent tool access."""

    def __init__(self, adapter: PolicyAdapter):
        self.adapter = adapter

    async def authorize_tool_access(
        self,
        agent: dict,
        blueprint: dict,
        user: dict,
        session: dict,
        runtime: dict,
        tool_id: str,
        operation: str,
        requested_scopes: list[str],
        environment: str = "development",
    ) -> PolicyOutput:
        """Evaluate whether an agent may access a tool with the given scopes."""
        policy_input = PolicyInput(
            agent=agent,
            blueprint=blueprint,
            user=user,
            session=session,
            runtime=runtime,
            tool={"id": tool_id},
            action={
                "operation": operation,
                "requested_scopes": requested_scopes,
            },
            environment={"name": environment},
        )
        return await self.adapter.evaluate(policy_input)
```

### 6. apps/identity_api/api/authorization.py
```python
"""Authorization endpoint — validates session tokens and evaluates policy."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.settings import Settings
from packages.token_library.validator import validate_session_token
from packages.policy_client.python_adapter import PythonPolicyAdapter
from packages.policy_client.opa_adapter import OPAAdapter
from apps.identity_api.dependencies import get_db, get_settings
from apps.identity_api.services.policy_service import PolicyService
from apps.identity_api.repositories.agent_repo import AgentRepository
from apps.identity_api.repositories.blueprint_repo import BlueprintRepository
from packages.identity_models.session import AgentSession

router = APIRouter(prefix="/v1", tags=["authorization"])


class AuthorizeRequest(BaseModel):
    session_token: str
    tool: str
    operation: str
    resource: dict = Field(default_factory=dict)


class AuthorizeResponse(BaseModel):
    decision: str
    effective_scopes: list[str]
    reason: str
    decision_id: str
    obligations: list[str]


async def get_policy_adapter(settings: Settings = Depends(get_settings)):
    """Try OPA first, fall back to Python adapter."""
    adapter = OPAAdapter(settings)
    if await adapter.health():
        return adapter
    await adapter.close()
    return PythonPolicyAdapter()


@router.post("/authorize", response_model=AuthorizeResponse)
async def authorize(
    data: AuthorizeRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    adapter=Depends(get_policy_adapter),
):
    # 1. Validate session token
    try:
        claims = validate_session_token(data.session_token, settings)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # 2. Look up session — verify not revoked
    session_id = claims.get("jti")
    session = await db.get(AgentSession, UUID(session_id)) if session_id else None
    if not session:
        raise HTTPException(status_code=401, detail="Session not found")
    if session.revoked_at:
        raise HTTPException(status_code=401, detail="Session has been revoked")

    # 3. Look up agent and blueprint
    repo = AgentRepository(db)
    agent = await repo.get_by_id(session.agent_id)
    if not agent:
        raise HTTPException(status_code=401, detail="Agent not found")

    bp_repo = BlueprintRepository(db)
    blueprint = await bp_repo.get_by_id(agent.blueprint_id)
    if not blueprint:
        raise HTTPException(status_code=401, detail="Blueprint not found")

    # 4. Build policy input
    policy_service = PolicyService(adapter)
    result = await policy_service.authorize_tool_access(
        agent={
            "id": str(agent.id),
            "status": agent.status.value,
            "scopes": session.effective_scopes,
        },
        blueprint={
            "id": str(blueprint.id),
            "slug": blueprint.slug,
            "status": blueprint.status.value,
            "max_scopes": blueprint.max_scopes,
            "approved_environments": blueprint.approved_environments,
            "approved_models": blueprint.approved_models,
        },
        user={
            "id": session.acting_user_id or "",
            "scopes": [],  # User scopes from delegation would go here
        },
        session={
            "id": str(session.id),
            "model_id": session.model_id,
            "trace_id": session.trace_id,
        },
        runtime={"environment": "development"},  # From attestation
        tool_id=data.tool,
        operation=data.operation,
        requested_scopes=claims.get("scopes", []),
    )

    return AuthorizeResponse(
        decision=result.decision,
        effective_scopes=result.effective_scopes,
        reason=result.reason,
        decision_id=f"dec_{session.trace_id}",
        obligations=result.obligations,
    )
```

### 7. apps/identity_api/main.py — register authorization router
Add:
```python
from apps.identity_api.api import authorization
app.include_router(authorization.router)
```

### 8. policies/agent_access.rego
```rego
package agent_identity.tool_access

import rego.v1

default allow := false
default deny_reason := "Access denied by default — no matching allow rule"

# Allow read-only GitHub operations
allow if {
    input.agent.status == "active"
    input.blueprint.status == "active"
    input.tool.id == "github"
    input.action.operation == "search_code"
    "repo:read" in input.action.requested_scopes
}

# Allow issue read for all agents
allow if {
    input.agent.status == "active"
    input.blueprint.status == "active"
    input.tool.id == "github"
    input.action.operation == "list_issues"
    "issues:read" in input.action.requested_scopes
}

# Allow Confluence read
allow if {
    input.agent.status == "active"
    input.blueprint.status == "active"
    input.tool.id == "confluence"
    input.action.operation == "search"
    "pages:read" in input.action.requested_scopes
}

# Deny write operations for research agents
deny_reason := "Research agents cannot perform write operations" if {
    input.blueprint.slug == "research-agent"
    some scope in input.action.requested_scopes
    endswith(scope, ":write")
}

# Compute effective scopes (intersection)
effective_scopes := [scope |
    some scope in input.action.requested_scopes
    scope in input.agent.scopes
    scope in input.blueprint.max_scopes
]
```

### 9. Tests — tests/unit/test_scope_intersection.py
```python
"""Unit tests for scope intersection logic."""

import pytest
from packages.policy_client.python_adapter import PythonPolicyAdapter
from packages.policy_client.models import PolicyInput


@pytest.fixture
def adapter():
    return PythonPolicyAdapter()


@pytest.mark.asyncio
async def test_allow_read_for_active_agent(adapter):
    result = await adapter.evaluate(PolicyInput(
        agent={"status": "active", "scopes": ["repo:read"]},
        blueprint={"status": "active", "max_scopes": ["repo:read"], "approved_environments": ["development"]},
        user={"scopes": ["repo:read"]},
        tool={"id": "github"},
        action={"operation": "search_code", "requested_scopes": ["repo:read"]},
        runtime={"environment": "development"},
    ))
    assert result.decision == "allow"
    assert "repo:read" in result.effective_scopes


@pytest.mark.asyncio
async def test_deny_inactive_agent(adapter):
    result = await adapter.evaluate(PolicyInput(
        agent={"status": "suspended", "scopes": ["repo:read"]},
        blueprint={"status": "active", "max_scopes": ["repo:read"]},
        tool={"id": "github"},
        action={"operation": "search_code", "requested_scopes": ["repo:read"]},
    ))
    assert result.decision == "deny"


@pytest.mark.asyncio
async def test_deny_research_agent_write(adapter):
    result = await adapter.evaluate(PolicyInput(
        agent={"status": "active", "scopes": ["issues:write"]},
        blueprint={"status": "active", "slug": "research-agent", "max_scopes": ["issues:write"]},
        tool={"id": "github"},
        action={"operation": "create_issue", "requested_scopes": ["issues:write"]},
    ))
    assert result.decision == "deny"
    assert "Research" in result.reason


@pytest.mark.asyncio
async def test_deny_unknown_tool(adapter):
    result = await adapter.evaluate(PolicyInput(
        agent={"status": "active", "scopes": ["admin:all"]},
        blueprint={"status": "active", "max_scopes": ["admin:all"]},
        tool={"id": "dangerous_tool"},
        action={"operation": "do_bad_thing", "requested_scopes": ["admin:all"]},
    ))
    assert result.decision == "deny"
    assert "Unknown tool" in result.reason


@pytest.mark.asyncio
async def test_scope_intersection_reduces(adapter):
    """Requested 3 scopes, agent only has 2, blueprint has 1 — effective = 1."""
    result = await adapter.evaluate(PolicyInput(
        agent={"status": "active", "scopes": ["repo:read", "issues:read"]},
        blueprint={"status": "active", "max_scopes": ["repo:read"], "approved_environments": []},
        tool={"id": "github"},
        action={"operation": "search_code", "requested_scopes": ["repo:read", "issues:read", "issues:write"]},
    ))
    assert result.decision == "allow"
    assert result.effective_scopes == ["repo:read"]


@pytest.mark.asyncio
async def test_deny_wrong_environment(adapter):
    result = await adapter.evaluate(PolicyInput(
        agent={"status": "active", "scopes": ["repo:read"]},
        blueprint={"status": "active", "max_scopes": ["repo:read"], "approved_environments": ["staging"]},
        tool={"id": "github"},
        action={"operation": "search_code", "requested_scopes": ["repo:read"]},
        runtime={"environment": "production"},
    ))
    assert result.decision == "deny"
    assert "Environment" in result.reason
```

### 10. Tests — tests/integration/test_authorization_api.py
```python
"""Integration tests for the /v1/authorize endpoint."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from packages.attestation.verifier import AttestationVerifier


def make_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()
    return private_pem, public_pem


async def setup_agent_with_session(client: AsyncClient, slug: str, scopes: list[str]):
    """Helper: create blueprint, agent, activate both, create session, return token."""
    private_pem, public_pem = make_keypair()

    bp_r = await client.post("/v1/blueprints", json={"slug": slug, "name": slug, "max_scopes": scopes},
        headers={"X-Admin-API-Key": "test-admin-key"})
    bp_id = bp_r.json()["id"]
    await client.post(f"/v1/blueprints/{bp_id}/activate", headers={"X-Admin-API-Key": "test-admin-key"})

    agent_r = await client.post("/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test", "public_key": public_pem},
        headers={"X-Admin-API-Key": "test-admin-key"})
    agent_id = agent_r.json()["id"]
    await client.post(f"/v1/agents/{agent_id}/activate", headers={"X-Admin-API-Key": "test-admin-key"})

    claims = {"agent_id": agent_id, "container_digest": "sha256:abc", "git_commit": "abc123",
        "environment": "development", "host_id": "docker-01", "framework": "hermes",
        "framework_version": "0.4.0", "model": "deepseek-chat", "prompt_version": "v1",
        "issued_at": datetime.now(timezone.utc).isoformat(), "nonce": str(uuid.uuid4())}
    sig = AttestationVerifier.sign_attestation(claims, private_pem)

    sess_r = await client.post("/v1/sessions", json={
        "agent_id": agent_id, "acting_user_id": "usr_test",
        "requested_scopes": scopes, "model_id": "deepseek-chat",
        "runtime_attestation": {**claims, "signature": sig}})
    return sess_r.json()["token"]


@pytest.mark.asyncio
async def test_authorize_allowed_read(client: AsyncClient):
    token = await setup_agent_with_session(client, "auth-test-bp", ["repo:read"])
    r = await client.post("/v1/authorize", json={
        "session_token": token,
        "tool": "github",
        "operation": "search_code",
        "resource": {"repository": "rmax-ai/example"},
    })
    assert r.status_code == 200
    data = r.json()
    assert data["decision"] == "allow"
    assert "repo:read" in data["effective_scopes"]


@pytest.mark.asyncio
async def test_authorize_denied_write_for_research(client: AsyncClient):
    token = await setup_agent_with_session(client, "research-agent", ["issues:write"])
    r = await client.post("/v1/authorize", json={
        "session_token": token,
        "tool": "github",
        "operation": "create_issue",
    })
    assert r.status_code == 200
    assert r.json()["decision"] == "deny"


@pytest.mark.asyncio
async def test_authorize_invalid_token(client: AsyncClient):
    r = await client.post("/v1/authorize", json={
        "session_token": "not.a.valid.token",
        "tool": "github",
        "operation": "search_code",
    })
    assert r.status_code == 401
```

### 11. Tests — tests/unit/test_policy_properties.py
Property-based tests using Hypothesis:
```python
"""Property-based tests for policy invariants using Hypothesis."""

import pytest
from hypothesis import given, strategies as st, assume

from packages.policy_client.python_adapter import PythonPolicyAdapter
from packages.policy_client.models import PolicyInput


@pytest.fixture
def adapter():
    return PythonPolicyAdapter()


statuses = st.sampled_from(["active", "suspended", "revoked", "draft"])
scopes_list = st.lists(
    st.sampled_from(["repo:read", "repo:write", "issues:read", "issues:write", "pages:read", "pages:write"]),
    min_size=0, max_size=4, unique=True
)
environments = st.sampled_from(["development", "staging", "production", ""])
slugs = st.sampled_from(["research-agent", "support-agent", "deployment-agent", "custom-agent"])


@given(statuses, scopes_list, scopes_list)
@pytest.mark.asyncio
async def test_effective_scopes_are_subset_of_requested(adapter, agent_status, agent_scopes, requested_scopes):
    assume(len(requested_scopes) > 0)
    result = await adapter.evaluate(PolicyInput(
        agent={"status": agent_status, "scopes": agent_scopes},
        blueprint={"status": "active", "max_scopes": agent_scopes, "slug": "custom-agent"},
        tool={"id": "github"},
        action={"operation": "search_code", "requested_scopes": requested_scopes},
    ))
    if result.decision == "allow":
        assert set(result.effective_scopes) <= set(requested_scopes)


@given(statuses, scopes_list)
@pytest.mark.asyncio
async def test_revoked_agent_always_denied(adapter, agent_status, scopes):
    assume(agent_status != "active")
    result = await adapter.evaluate(PolicyInput(
        agent={"status": agent_status, "scopes": scopes},
        blueprint={"status": "active", "max_scopes": scopes},
        tool={"id": "github"},
        action={"operation": "search_code", "requested_scopes": scopes},
    ))
    assert result.decision == "deny"
```

## What NOT to modify
- Existing files not listed above
- packages/common/, packages/token_library/ (except as noted)
- apps/identity_api/repositories/
- apps/identity_api/services/session_service.py
- apps/identity_api/api/{blueprints,agents,sessions,delegations}.py
- tests/ existing files

## Verification
1. `PYTHONPATH=. uv run pytest tests/ -v` — all tests pass (36 existing + new ones)
2. `PYTHONPATH=. uv run ruff check packages/ apps/ tests/` — clean
3. `PYTHONPATH=. uv run ruff format packages/ apps/ tests/` — clean
