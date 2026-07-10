# Phase 2: Sessions and Tokens

You are implementing Phase 2 of Agent Identity Lab. Phase 1 is complete — the codebase has working Blueprint and Agent CRUD APIs with 19 passing tests.

**Context files to read first:**
- `SPEC.md` section 5.4 (Agent Session), 5.5 (Runtime Attestation), 5.7 (Delegation Grant), 7.3 (Session Creation), 7.4 (Runtime Attestation), 7.5 (Delegation), 12 (Token Model)
- `packages/common/models.py` — Base, TimestampMixin
- `packages/common/enums.py` — existing enums
- `packages/common/settings.py` — JWT settings already defined
- `packages/identity_models/agent.py` — AgentIdentity model
- `apps/identity_api/dependencies.py` — get_db, require_admin
- `apps/identity_api/main.py` — FastAPI app

**Tech stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async, PyJWT, cryptography

**Test command:** `PYTHONPATH=. uv run pytest tests/ -v`
**Lint:** `PYTHONPATH=. uv run ruff check packages/ apps/ tests/`
**Format:** `PYTHONPATH=. uv run ruff format packages/ apps/ tests/`

## Files to Create

### 1. packages/attestation/models.py
```python
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from packages.common.models import Base, TimestampMixin, new_uuid
from packages.common.enums import VerificationResult


class RuntimeAttestation(Base, TimestampMixin):
    __tablename__ = "runtime_attestations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_identities.id"), index=True)
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
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_result: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
```

### 2. packages/attestation/verifier.py
```python
"""Runtime attestation verification."""

import json
import time
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

from packages.attestation.models import RuntimeAttestation
from packages.common.enums import VerificationResult


class AttestationVerifier:
    """Verifies signed runtime attestation claims."""

    NONCE_SEEN: set[str] = set()
    MAX_CLOCK_SKEW_SECONDS = 300  # 5 minutes

    @classmethod
    def verify(
        cls,
        attestation_data: dict[str, Any],
        signature: str,
        public_key_pem: str,
        expected_agent_id: str,
    ) -> tuple[VerificationResult, str]:
        """Verify attestation claims and signature.

        Returns (result, reason).
        """
        # 1. Verify signature
        canonical = json.dumps(attestation_data, sort_keys=True)
        try:
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            public_key.verify(
                bytes.fromhex(signature),
                canonical.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except (InvalidSignature, ValueError) as e:
            return VerificationResult.REJECTED, f"Signature verification failed: {e}"

        # 2. Check timestamp freshness
        issued_at_str = attestation_data.get("issued_at")
        if not issued_at_str:
            return VerificationResult.REJECTED, "Missing issued_at claim"

        try:
            issued_at = datetime.fromisoformat(issued_at_str.replace("Z", "+00:00"))
        except ValueError:
            return VerificationResult.REJECTED, "Invalid issued_at format"

        now = datetime.now(timezone.utc)
        skew = abs((now - issued_at).total_seconds())
        if skew > cls.MAX_CLOCK_SKEW_SECONDS:
            return VerificationResult.REJECTED, f"Timestamp skew too large: {skew:.0f}s"

        # 3. Verify nonce uniqueness
        nonce = attestation_data.get("nonce")
        if not nonce:
            return VerificationResult.REJECTED, "Missing nonce claim"
        if nonce in cls.NONCE_SEEN:
            return VerificationResult.REJECTED, f"Nonce already seen: {nonce}"
        cls.NONCE_SEEN.add(nonce)

        # 4. Verify agent ID match
        agent_id = attestation_data.get("agent_id")
        if agent_id != expected_agent_id:
            return VerificationResult.REJECTED, f"Agent ID mismatch: {agent_id} != {expected_agent_id}"

        # 5. Verify required claims
        required = [
            "container_digest", "git_commit", "environment",
            "host_id", "framework", "framework_version",
            "model", "prompt_version",
        ]
        missing = [c for c in required if c not in attestation_data]
        if missing:
            return VerificationResult.REJECTED, f"Missing required claims: {missing}"

        return VerificationResult.VERIFIED, "All checks passed"

    @staticmethod
    def sign_attestation(claims: dict[str, Any], private_key_pem: str) -> str:
        """Sign attestation claims with private key. Returns hex signature."""
        canonical = json.dumps(claims, sort_keys=True)
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None
        )
        sig = private_key.sign(
            canonical.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return sig.hex()
```

### 3. packages/identity_models/delegation.py
```python
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from packages.common.models import Base, TimestampMixin, new_uuid


class DelegationGrant(Base, TimestampMixin):
    __tablename__ = "delegation_grants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(256), index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_identities.id"))
    scopes: Mapped[list] = mapped_column(JSONB, default=list)
    resource_constraints: Mapped[dict] = mapped_column(JSONB, default=dict)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 4. packages/identity_models/session.py
```python
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from packages.common.models import Base, TimestampMixin, new_uuid


class AgentSession(Base, TimestampMixin):
    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_identities.id"), index=True)
    acting_user_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    delegation_grant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("delegation_grants.id"), nullable=True)
    model_id: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(64))
    runtime_attestation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runtime_attestations.id"))
    requested_scopes: Mapped[list] = mapped_column(JSONB, default=list)
    effective_scopes: Mapped[list] = mapped_column(JSONB, default=list)
    policy_version: Mapped[str] = mapped_column(String(64), default="0.0.0")
    trace_id: Mapped[str] = mapped_column(String(128), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 5. packages/token_library/issuer.py
```python
"""JWT token issuance for Agent Session Tokens."""

import uuid
from datetime import datetime, timezone

import jwt

from packages.common.settings import Settings
from packages.identity_models.session import AgentSession


def load_private_key(settings: Settings) -> str:
    with open(settings.jwt_private_key_path) as f:
        return f.read()


def issue_session_token(session: AgentSession, settings: Settings) -> str:
    """Issue a signed JWT for an agent session."""
    private_key = load_private_key(settings)
    now = datetime.now(timezone.utc)

    claims = {
        "iss": settings.jwt_issuer,
        "sub": f"agent:{session.agent_id}",
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(session.expires_at.timestamp()),
        "jti": str(session.id),
        "agent_id": str(session.agent_id),
        "blueprint_id": "unknown",  # populated by caller with actual blueprint
        "acting_user": session.acting_user_id,
        "delegation_id": str(session.delegation_grant_id) if session.delegation_grant_id else None,
        "scopes": session.effective_scopes,
        "model": session.model_id,
        "prompt_version": session.prompt_version,
        "trace_id": session.trace_id,
        "policy_version": session.policy_version,
    }

    return jwt.encode(claims, private_key, algorithm=settings.jwt_algorithm)
```

### 6. packages/token_library/validator.py
```python
"""JWT token validation for Agent Session Tokens."""

from typing import Any

import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidSignatureError,
    InvalidTokenError,
)

from packages.common.settings import Settings


def load_public_key(settings: Settings) -> str:
    with open(settings.jwt_public_key_path) as f:
        return f.read()


def validate_session_token(token: str, settings: Settings) -> dict[str, Any]:
    """Validate and decode an Agent Session Token.

    Returns the claims dict if valid.
    Raises ValueError with a descriptive message if invalid.
    """
    public_key = load_public_key(settings)

    # Reject algorithm substitution
    options = {"require": ["exp", "iat", "jti", "iss", "aud", "sub"]}

    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options=options,
        )
    except ExpiredSignatureError:
        raise ValueError("Token has expired")
    except InvalidAudienceError:
        raise ValueError("Invalid token audience")
    except InvalidSignatureError:
        raise ValueError("Invalid token signature")
    except InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")

    # Verify required custom claims
    required_claims = ["agent_id", "scopes", "trace_id"]
    missing = [c for c in required_claims if c not in claims]
    if missing:
        raise ValueError(f"Missing required claims: {missing}")

    # Verify scopes is a list
    if not isinstance(claims.get("scopes"), list):
        raise ValueError("scopes claim must be a list")

    return claims
```

### 7. apps/identity_api/services/session_service.py
```python
"""Session creation and management service."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.enums import AgentStatus, VerificationResult
from packages.common.settings import Settings
from packages.identity_models.agent import AgentIdentity
from packages.identity_models.delegation import DelegationGrant
from packages.identity_models.session import AgentSession
from packages.attestation.models import RuntimeAttestation
from packages.attestation.verifier import AttestationVerifier
from packages.token_library.issuer import issue_session_token
from apps.identity_api.repositories.agent_repo import AgentRepository


class SessionError(Exception):
    pass


class SessionService:
    def __init__(self, session: AsyncSession, settings: Settings):
        self.db = session
        self.settings = settings

    async def create_session(
        self,
        agent_id: uuid.UUID,
        acting_user_id: str | None,
        delegation_grant_id: uuid.UUID | None,
        requested_scopes: list[str],
        requested_ttl_seconds: int,
        model_id: str,
        prompt_version: str,
        attestation_data: dict,
        attestation_signature: str,
    ) -> tuple[AgentSession, str]:
        """Create an agent session and return (session, token)."""
        repo = AgentRepository(self.db)

        # 1. Verify agent exists and is ACTIVE
        agent = await repo.get_by_id(agent_id)
        if not agent:
            raise SessionError("Agent not found")
        if agent.status != AgentStatus.ACTIVE:
            raise SessionError(f"Agent is not active (status: {agent.status})")
        if not agent.public_key:
            raise SessionError("Agent has no registered public key")

        # 2. Verify runtime attestation
        result, reason = AttestationVerifier.verify(
            attestation_data,
            attestation_signature,
            agent.public_key,
            str(agent_id),
        )
        if result != VerificationResult.VERIFIED:
            raise SessionError(f"Attestation rejected: {reason}")

        # 3. Store attestation record
        attestation = RuntimeAttestation(
            agent_id=agent_id,
            container_digest=attestation_data["container_digest"],
            git_commit=attestation_data["git_commit"],
            environment=attestation_data["environment"],
            host_id=attestation_data["host_id"],
            framework=attestation_data["framework"],
            framework_version=attestation_data["framework_version"],
            model_id=attestation_data.get("model", model_id),
            prompt_version=attestation_data.get("prompt_version", prompt_version),
            nonce=attestation_data["nonce"],
            signature=attestation_signature,
            issued_at=datetime.fromisoformat(
                attestation_data["issued_at"].replace("Z", "+00:00")
            ),
            verified_at=datetime.now(timezone.utc),
            verification_result=VerificationResult.VERIFIED,
        )
        self.db.add(attestation)
        await self.db.flush()

        # 4. Validate delegation grant if present
        if delegation_grant_id:
            dg = await self.db.get(DelegationGrant, delegation_grant_id)
            if not dg:
                raise SessionError("Delegation grant not found")
            if dg.revoked_at:
                raise SessionError("Delegation grant has been revoked")
            if dg.expires_at < datetime.now(timezone.utc):
                raise SessionError("Delegation grant has expired")
            if dg.agent_id != agent_id:
                raise SessionError("Delegation grant does not match agent")

        # 5. Compute effective scopes (Phase 3 will expand this)
        effective_scopes = requested_scopes  # For now, pass-through

        # 6. Enforce TTL cap
        ttl = min(requested_ttl_seconds, self.settings.session_max_ttl_seconds)

        # 7. Create session
        now = datetime.now(timezone.utc)
        session = AgentSession(
            agent_id=agent_id,
            acting_user_id=acting_user_id,
            delegation_grant_id=delegation_grant_id,
            model_id=model_id,
            prompt_version=prompt_version,
            runtime_attestation_id=attestation.id,
            requested_scopes=requested_scopes,
            effective_scopes=effective_scopes,
            policy_version="0.1.0",
            trace_id=f"trace_{uuid.uuid4().hex[:16]}",
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl),
        )
        self.db.add(session)
        await self.db.flush()

        # 8. Issue token with blueprint info
        token = issue_session_token(session, self.settings)
        # Patch the blueprint_id claim
        import jwt as jwt_lib
        private_key = open(self.settings.jwt_private_key_path).read()
        claims = jwt_lib.decode(token, options={"verify_signature": False})
        claims["blueprint_id"] = f"blueprint-{agent.blueprint_id}"
        token = jwt_lib.encode(claims, private_key, algorithm=self.settings.jwt_algorithm)

        return session, token

    async def revoke_session(self, session_id: uuid.UUID) -> AgentSession:
        s = await self.db.get(AgentSession, session_id)
        if not s:
            raise SessionError("Session not found")
        if s.revoked_at:
            raise SessionError("Session already revoked")
        s.revoked_at = datetime.now(timezone.utc)
        await self.db.commit()
        return s
```

That service has a bug — it decodes and re-encodes to add blueprint_id claim after issuance. Let's fix it: modify `packages/token_library/issuer.py` to accept blueprint_id as a parameter.

### 8. Update: packages/token_library/issuer.py (replacement)
Replace the entire file with:
```python
"""JWT token issuance for Agent Session Tokens."""

import uuid
from datetime import datetime, timezone

import jwt

from packages.common.settings import Settings
from packages.identity_models.session import AgentSession


def load_private_key(settings: Settings) -> str:
    with open(settings.jwt_private_key_path) as f:
        return f.read()


def issue_session_token(
    session: AgentSession,
    settings: Settings,
    blueprint_id: str = "unknown",
) -> str:
    """Issue a signed JWT for an agent session."""
    private_key = load_private_key(settings)
    now = datetime.now(timezone.utc)

    claims = {
        "iss": settings.jwt_issuer,
        "sub": f"agent:{session.agent_id}",
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(session.expires_at.timestamp()),
        "jti": str(session.id),
        "agent_id": str(session.agent_id),
        "blueprint_id": blueprint_id,
        "acting_user": session.acting_user_id,
        "delegation_id": str(session.delegation_grant_id) if session.delegation_grant_id else None,
        "scopes": session.effective_scopes,
        "model": session.model_id,
        "prompt_version": session.prompt_version,
        "trace_id": session.trace_id,
        "policy_version": session.policy_version,
    }

    return jwt.encode(claims, private_key, algorithm=settings.jwt_algorithm)
```

And update the session_service.py call to:
```python
token = issue_session_token(session, self.settings, blueprint_id=f"blueprint-{agent.blueprint_id}")
```

### 9. apps/identity_api/api/sessions.py
```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.settings import Settings
from apps.identity_api.dependencies import get_db, get_settings
from apps.identity_api.services.session_service import SessionService, SessionError

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


class SessionCreateRequest(BaseModel):
    agent_id: UUID
    acting_user_id: str | None = None
    delegation_grant_id: UUID | None = None
    requested_scopes: list[str] = Field(default_factory=list)
    requested_ttl_seconds: int = Field(ge=1, le=1800, default=900)
    model_id: str
    prompt_version: str = "v1"
    runtime_attestation: dict = Field(default_factory=dict)


class SessionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    acting_user_id: str | None
    token: str
    trace_id: str
    effective_scopes: list[str]
    issued_at: str
    expires_at: str

    model_config = {"from_attributes": True}


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    svc = SessionService(db, settings)
    attestation_data = data.runtime_attestation
    signature = attestation_data.pop("signature", "")

    try:
        session, token = await svc.create_session(
            agent_id=data.agent_id,
            acting_user_id=data.acting_user_id,
            delegation_grant_id=data.delegation_grant_id,
            requested_scopes=data.requested_scopes,
            requested_ttl_seconds=data.requested_ttl_seconds,
            model_id=data.model_id,
            prompt_version=data.prompt_version,
            attestation_data=attestation_data,
            attestation_signature=signature,
        )
    except SessionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SessionResponse(
        id=session.id,
        agent_id=session.agent_id,
        acting_user_id=session.acting_user_id,
        token=token,
        trace_id=session.trace_id,
        effective_scopes=session.effective_scopes,
        issued_at=session.issued_at.isoformat(),
        expires_at=session.expires_at.isoformat(),
    )


@router.get("/{id}")
async def get_session(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    from packages.identity_models.session import AgentSession
    s = await db.get(AgentSession, id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": str(s.id),
        "agent_id": str(s.agent_id),
        "acting_user_id": s.acting_user_id,
        "status": "revoked" if s.revoked_at else "active",
        "effective_scopes": s.effective_scopes,
        "trace_id": s.trace_id,
        "issued_at": s.issued_at.isoformat(),
        "expires_at": s.expires_at.isoformat(),
        "revoked_at": s.revoked_at.isoformat() if s.revoked_at else None,
    }


@router.post("/{id}/revoke")
async def revoke_session(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    svc = SessionService(db, settings)
    try:
        await svc.revoke_session(id)
        return {"status": "revoked", "id": str(id)}
    except SessionError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 10. apps/identity_api/api/delegations.py
```python
from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from packages.identity_models.delegation import DelegationGrant
from apps.identity_api.dependencies import get_db, require_admin

router = APIRouter(prefix="/v1/delegations", tags=["delegations"])


class DelegationCreate(BaseModel):
    user_id: str
    agent_id: UUID
    scopes: list[str] = Field(default_factory=list)
    resource_constraints: dict = Field(default_factory=dict)
    ttl_seconds: int = Field(ge=1, le=86400, default=1800)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_delegation(
    data: DelegationCreate,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    now = datetime.now(timezone.utc)
    dg = DelegationGrant(
        user_id=data.user_id,
        agent_id=data.agent_id,
        scopes=data.scopes,
        resource_constraints=data.resource_constraints,
        issued_at=now,
        expires_at=now + timedelta(seconds=data.ttl_seconds),
    )
    session.add(dg)
    await session.commit()
    await session.refresh(dg)
    return {"id": str(dg.id), "expires_at": dg.expires_at.isoformat()}


@router.get("/{id}")
async def get_delegation(id: UUID, session: AsyncSession = Depends(get_db)):
    dg = await session.get(DelegationGrant, id)
    if not dg:
        raise HTTPException(status_code=404, detail="Delegation not found")
    return {
        "id": str(dg.id),
        "user_id": dg.user_id,
        "agent_id": str(dg.agent_id),
        "scopes": dg.scopes,
        "issued_at": dg.issued_at.isoformat(),
        "expires_at": dg.expires_at.isoformat(),
        "revoked": dg.revoked_at is not None,
    }


@router.post("/{id}/revoke")
async def revoke_delegation(
    id: UUID,
    session: AsyncSession = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    dg = await session.get(DelegationGrant, id)
    if not dg:
        raise HTTPException(status_code=404, detail="Delegation not found")
    if dg.revoked_at:
        raise HTTPException(status_code=400, detail="Delegation already revoked")
    dg.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "revoked", "id": str(id)}
```

### 11. apps/identity_api/main.py — add router registrations
Add these imports and registrations (after existing ones):
```python
from apps.identity_api.api import sessions, delegations

app.include_router(sessions.router)
app.include_router(delegations.router)
```

### 12. Tests — tests/unit/test_token_validation.py
```python
"""Unit tests for JWT token issuance and validation."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from packages.common.settings import Settings
from packages.token_library.issuer import issue_session_token
from packages.token_library.validator import validate_session_token
from packages.identity_models.session import AgentSession


@pytest.fixture
def test_settings(tmp_path):
    """Generate test RSA keys and return settings pointing to them."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    return Settings(
        jwt_private_key_path=str(private_path),
        jwt_public_key_path=str(public_path),
        jwt_algorithm="RS256",
        jwt_issuer="agent-identity-lab",
        jwt_audience="mcp-gateway",
    )


def make_session(**overrides):
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "acting_user_id": "usr_test",
        "delegation_grant_id": None,
        "model_id": "deepseek-chat",
        "prompt_version": "v1",
        "requested_scopes": ["repo:read"],
        "effective_scopes": ["repo:read"],
        "policy_version": "0.1.0",
        "trace_id": "trace_test123",
        "issued_at": now,
        "expires_at": now + timedelta(seconds=900),
        "revoked_at": None,
    }
    defaults.update(overrides)
    return AgentSession(**defaults)


class TestTokenIssuance:
    def test_issue_and_validate(self, test_settings):
        session = make_session()
        token = issue_session_token(session, test_settings, blueprint_id="bp-test:v1")

        claims = validate_session_token(token, test_settings)
        assert claims["agent_id"] == str(session.agent_id)
        assert claims["scopes"] == ["repo:read"]
        assert claims["blueprint_id"] == "bp-test:v1"

    def test_expired_token_rejected(self, test_settings):
        session = make_session(
            issued_at=datetime.now(timezone.utc) - timedelta(hours=2),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        token = issue_session_token(session, test_settings)

        with pytest.raises(ValueError, match="expired"):
            validate_session_token(token, test_settings)

    def test_wrong_audience_rejected(self, test_settings):
        session = make_session()
        token = issue_session_token(session, test_settings)

        wrong_settings = Settings(
            jwt_public_key_path=test_settings.jwt_public_key_path,
            jwt_algorithm="RS256",
            jwt_issuer="agent-identity-lab",
            jwt_audience="wrong-audience",
        )
        with pytest.raises(ValueError, match="audience"):
            validate_session_token(token, wrong_settings)

    def test_wrong_signature_rejected(self, test_settings):
        session = make_session()
        token = issue_session_token(session, test_settings)
        # Tamper with the token
        tampered = token[:-4] + "XXXX"

        with pytest.raises(ValueError, match="signature"):
            validate_session_token(tampered, test_settings)

    def test_machine_only_session_no_user(self, test_settings):
        session = make_session(acting_user_id=None)
        token = issue_session_token(session, test_settings)
        claims = validate_session_token(token, test_settings)
        assert claims["acting_user"] is None
```

### 13. Tests — tests/unit/test_attestation.py
```python
"""Unit tests for runtime attestation verification."""

import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from packages.common.enums import VerificationResult
from packages.attestation.verifier import AttestationVerifier


def make_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem.decode(), public_pem.decode()


def make_attestation(agent_id, **overrides):
    data = {
        "agent_id": agent_id,
        "container_digest": "sha256:abc123",
        "git_commit": "abc123def456",
        "environment": "development",
        "host_id": "docker-local-01",
        "framework": "hermes",
        "framework_version": "0.4.0",
        "model": "deepseek-chat",
        "prompt_version": "research-v3",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "nonce": str(uuid.uuid4()),
    }
    data.update(overrides)
    return data


class TestAttestationVerifier:
    def test_valid_attestation(self):
        agent_id = str(uuid.uuid4())
        private_pem, public_pem = make_keypair()
        claims = make_attestation(agent_id)
        sig = AttestationVerifier.sign_attestation(claims, private_pem)

        result, reason = AttestationVerifier.verify(claims, sig, public_pem, agent_id)
        assert result == VerificationResult.VERIFIED
        assert reason == "All checks passed"

    def test_agent_id_mismatch(self):
        agent_id = str(uuid.uuid4())
        private_pem, public_pem = make_keypair()
        claims = make_attestation(agent_id)
        sig = AttestationVerifier.sign_attestation(claims, private_pem)

        result, reason = AttestationVerifier.verify(
            claims, sig, public_pem, str(uuid.uuid4())  # different agent
        )
        assert result == VerificationResult.REJECTED
        assert "Agent ID mismatch" in reason

    def test_replay_attack_blocked(self):
        agent_id = str(uuid.uuid4())
        private_pem, public_pem = make_keypair()
        claims = make_attestation(agent_id, nonce="replay-nonce-123")
        sig = AttestationVerifier.sign_attestation(claims, private_pem)

        result1, _ = AttestationVerifier.verify(claims, sig, public_pem, agent_id)
        assert result1 == VerificationResult.VERIFIED

        # Second attempt with same nonce
        result2, reason2 = AttestationVerifier.verify(claims, sig, public_pem, agent_id)
        assert result2 == VerificationResult.REJECTED
        assert "already seen" in reason2

    def test_missing_required_claim(self):
        agent_id = str(uuid.uuid4())
        private_pem, public_pem = make_keypair()
        claims = make_attestation(agent_id)
        del claims["container_digest"]
        sig = AttestationVerifier.sign_attestation(claims, private_pem)

        result, reason = AttestationVerifier.verify(claims, sig, public_pem, agent_id)
        assert result == VerificationResult.REJECTED
        assert "missing" in reason.lower()

    def test_invalid_signature(self):
        agent_id = str(uuid.uuid4())
        private_pem, public_pem = make_keypair()
        claims = make_attestation(agent_id)
        sig = AttestationVerifier.sign_attestation(claims, private_pem)
        # Corrupt the claims but keep the same signature
        claims["container_digest"] = "sha256:evil"

        result, reason = AttestationVerifier.verify(claims, sig, public_pem, agent_id)
        assert result == VerificationResult.REJECTED
        assert "Signature" in reason
```

### 14. Tests — tests/integration/test_session_api.py
```python
"""Integration tests for session creation with attestation."""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from packages.attestation.verifier import AttestationVerifier


def make_attestation(agent_id):
    """Create a valid signed attestation."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    claims = {
        "agent_id": agent_id,
        "container_digest": "sha256:abc123",
        "git_commit": "abc123def456",
        "environment": "development",
        "host_id": "docker-local-01",
        "framework": "hermes",
        "framework_version": "0.4.0",
        "model": "deepseek-chat",
        "prompt_version": "research-v3",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "nonce": str(uuid.uuid4()),
    }
    sig = AttestationVerifier.sign_attestation(claims, private_pem)
    return claims, sig, public_pem


@pytest.mark.asyncio
async def test_create_session_with_valid_attestation(client: AsyncClient):
    """Full session creation flow: blueprint → agent → attestation → session."""
    # 1. Create and activate a blueprint
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "session-bp", "name": "Session BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(
        f"/v1/blueprints/{bp_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    # 2. Create an agent with a key, activate it
    claims, sig, public_pem = make_attestation(str(uuid.uuid4()))
    agent_r = await client.post(
        "/v1/agents",
        json={
            "blueprint_id": bp_id,
            "owner_id": "usr_test",
            "public_key": public_pem,
        },
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]
    await client.post(
        f"/v1/agents/{agent_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    # 3. Create a session with attestation FOR THIS AGENT
    claims["agent_id"] = agent_id
    sig = AttestationVerifier.sign_attestation(
        claims,
        # Re-generate private key from the same keypair — for test simplicity,
        # use a fresh keypair and update the agent's key
        # Actually, let's create the keypair and agent in one step
    )

    # Re-do step 2 with the right keypair
    # Delete and recreate the agent with the matched key
    # (Simpler: generate keypair first, create agent with the public key)

    # Let's just verify the session creation fails with bad attestation for now
    bad_claims = {**claims, "agent_id": agent_id}
    bad_sig = "00" * 64  # bad signature

    r = await client.post(
        "/v1/sessions",
        json={
            "agent_id": agent_id,
            "acting_user_id": "usr_test",
            "requested_scopes": ["repo:read"],
            "requested_ttl_seconds": 900,
            "model_id": "deepseek-chat",
            "runtime_attestation": {**bad_claims, "signature": bad_sig},
        },
    )
    assert r.status_code == 400
    assert "attestation" in r.text.lower() or "signature" in r.text.lower()
```

Actually, that integration test is getting complicated with key management. Let's simplify — test session creation / revocation API shape rather than full crypto flow.

Write this simpler version:
```python
"""Integration tests for session API endpoints."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from packages.attestation.verifier import AttestationVerifier


@pytest.mark.asyncio
async def test_create_session_rejects_inactive_agent(client: AsyncClient):
    """Session creation must fail for non-active agents."""
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "sess-test-bp", "name": "Sess BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(
        f"/v1/blueprints/{bp_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    # Create agent but DON'T activate
    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]

    r = await client.post(
        "/v1/sessions",
        json={
            "agent_id": agent_id,
            "acting_user_id": "usr_test",
            "requested_scopes": ["repo:read"],
            "model_id": "deepseek-chat",
            "runtime_attestation": {"signature": "00" * 64},
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_session_requires_agent_exists(client: AsyncClient):
    r = await client.post(
        "/v1/sessions",
        json={
            "agent_id": str(uuid.uuid4()),
            "model_id": "deepseek-chat",
            "runtime_attestation": {"signature": "00" * 64},
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient):
    r = await client.get(f"/v1/sessions/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_delegation(client: AsyncClient):
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "deleg-bp", "name": "Deleg BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(f"/v1/blueprints/{bp_id}/activate", headers={"X-Admin-API-Key": "test-admin-key"})

    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]

    r = await client.post(
        "/v1/delegations",
        json={
            "user_id": "usr_test",
            "agent_id": agent_id,
            "scopes": ["repo:read"],
            "ttl_seconds": 1800,
        },
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert r.status_code == 201
    assert "id" in r.json()


@pytest.mark.asyncio
async def test_revoke_delegation(client: AsyncClient):
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "del-rev-bp", "name": "Del Rev BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(f"/v1/blueprints/{bp_id}/activate", headers={"X-Admin-API-Key": "test-admin-key"})

    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]

    dg_r = await client.post(
        "/v1/delegations",
        json={"user_id": "usr_test", "agent_id": agent_id, "scopes": ["repo:read"]},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    dg_id = dg_r.json()["id"]

    r = await client.post(f"/v1/delegations/{dg_id}/revoke", headers={"X-Admin-API-Key": "test-admin-key"})
    assert r.status_code == 200

    r2 = await client.get(f"/v1/delegations/{dg_id}")
    assert r2.json()["revoked"] is True
```

### 15. Tests — tests/integration/test_session_success.py
A separate test file for the full happy-path session creation (since it requires keypair setup):
```python
"""Happy-path session creation integration test."""

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
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return private_pem, public_pem


@pytest.mark.asyncio
async def test_full_session_creation_flow(client: AsyncClient):
    """End-to-end: blueprint → agent → attestation → session token."""
    private_pem, public_pem = make_keypair()

    # 1. Create + activate blueprint
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "full-flow-bp", "name": "Full Flow BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(
        f"/v1/blueprints/{bp_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    # 2. Create agent with the public key and activate
    agent_r = await client.post(
        "/v1/agents",
        json={
            "blueprint_id": bp_id,
            "owner_id": "usr_test",
            "public_key": public_pem,
        },
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]
    await client.post(
        f"/v1/agents/{agent_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    # 3. Create signed attestation
    claims = {
        "agent_id": agent_id,
        "container_digest": "sha256:abc123def456",
        "git_commit": "abc123def4567890",
        "environment": "development",
        "host_id": "docker-local-01",
        "framework": "hermes",
        "framework_version": "0.4.0",
        "model": "deepseek-chat",
        "prompt_version": "research-v3",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "nonce": str(uuid.uuid4()),
    }
    sig = AttestationVerifier.sign_attestation(claims, private_pem)

    # 4. Create session
    r = await client.post(
        "/v1/sessions",
        json={
            "agent_id": agent_id,
            "acting_user_id": "usr_test",
            "requested_scopes": ["repo:read"],
            "requested_ttl_seconds": 900,
            "model_id": "deepseek-chat",
            "prompt_version": "research-v3",
            "runtime_attestation": {**claims, "signature": sig},
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert "token" in data
    assert data["effective_scopes"] == ["repo:read"]
    assert data["acting_user_id"] == "usr_test"
    assert "trace_id" in data

    # 5. Verify token claims
    token = data["token"]
    import jwt as jwt_lib
    # Decode without verification (just to inspect claims)
    claims = jwt_lib.decode(token, options={"verify_signature": False})
    assert claims["agent_id"] == agent_id
    assert claims["scopes"] == ["repo:read"]
    assert claims["acting_user"] == "usr_test"


@pytest.mark.asyncio
async def test_revoke_session(client: AsyncClient):
    """Create a session, then revoke it."""
    private_pem, public_pem = make_keypair()

    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "revoke-sess-bp", "name": "Revoke BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(f"/v1/blueprints/{bp_id}/activate", headers={"X-Admin-API-Key": "test-admin-key"})

    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test", "public_key": public_pem},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]
    await client.post(f"/v1/agents/{agent_id}/activate", headers={"X-Admin-API-Key": "test-admin-key"})

    claims = {
        "agent_id": agent_id,
        "container_digest": "sha256:abc",
        "git_commit": "abc123",
        "environment": "development",
        "host_id": "docker-local-01",
        "framework": "hermes",
        "framework_version": "0.4.0",
        "model": "deepseek-chat",
        "prompt_version": "v1",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "nonce": str(uuid.uuid4()),
    }
    sig = AttestationVerifier.sign_attestation(claims, private_pem)

    r = await client.post(
        "/v1/sessions",
        json={
            "agent_id": agent_id,
            "acting_user_id": "usr_test",
            "requested_scopes": ["repo:read"],
            "model_id": "deepseek-chat",
            "runtime_attestation": {**claims, "signature": sig},
        },
    )
    assert r.status_code == 201
    session_id = r.json()["id"]

    # Revoke
    r2 = await client.post(f"/v1/sessions/{session_id}/revoke")
    assert r2.status_code == 200

    # Verify revoked
    r3 = await client.get(f"/v1/sessions/{session_id}")
    assert r3.json()["status"] == "revoked"
```

## What NOT to modify
- packages/common/settings.py
- packages/common/models.py
- packages/common/enums.py
- packages/identity_models/blueprint.py
- packages/identity_models/agent.py
- packages/identity_models/schemas.py
- apps/identity_api/repositories/
- apps/identity_api/api/blueprints.py
- apps/identity_api/api/agents.py
- tests/conftest.py
- tests/unit/test_enums.py
- tests/unit/test_blueprint_schemas.py
- tests/integration/test_blueprint_api.py
- tests/integration/test_agent_api.py
- pyproject.toml

## Verification
After writing all files, run:
```
PYTHONPATH=. uv run pytest tests/ -v
```
Expected: all tests pass (19 existing + new ones).

Then:
```
PYTHONPATH=. uv run ruff check packages/ apps/ tests/
PYTHONPATH=. uv run ruff format packages/ apps/ tests/
```
Fix any lint issues. Verify tests still pass.
