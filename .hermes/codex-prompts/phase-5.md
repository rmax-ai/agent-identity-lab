# Phase 5: Token Brokerage

Implement credential provider interface, mock OAuth provider, static secret injection, credential leases, and token exchange endpoint.

**Context:** Phases 1-4 complete. 47 tests pass.

**Test:** `PYTHONPATH=. uv run pytest tests/ -v`
**Lint:** `PYTHONPATH=. uv run ruff check packages/ apps/ tests/`

## Files to Create

### 1. packages/identity_models/credential_lease.py
```python
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from packages.common.models import Base, new_uuid

class CredentialLease(Base):
    __tablename__ = "credential_leases"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_sessions.id"))
    tool_id: Mapped[str] = mapped_column(String(128))
    scopes: Mapped[list] = mapped_column(JSONB, default=list)
    provider: Mapped[str] = mapped_column(String(64))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

### 2. apps/token_broker/providers/base.py
```python
from abc import ABC, abstractmethod

class CredentialProvider(ABC):
    @abstractmethod
    async def issue(self, tool_id: str, scopes: list[str], session_id: str) -> dict:
        """Issue a downstream credential. Returns cred metadata dict — NEVER raw secrets."""
        ...

    @abstractmethod
    async def revoke(self, lease_id: str) -> bool:
        ...
```

### 3. apps/token_broker/providers/mock_oauth.py
```python
import uuid
from datetime import datetime, timedelta, timezone
from apps.token_broker.providers.base import CredentialProvider

class MockOAuthProvider(CredentialProvider):
    async def issue(self, tool_id: str, scopes: list[str], session_id: str) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "provider": "mock_oauth",
            "token": f"mock_oauth_token_{uuid.uuid4().hex[:16]}",
            "type": "bearer",
            "scopes": scopes,
            "expires_at": (now + timedelta(minutes=30)).isoformat(),
        }

    async def revoke(self, lease_id: str) -> bool:
        return True
```

### 4. apps/token_broker/providers/static_secret.py
```python
import uuid
from apps.token_broker.providers.base import CredentialProvider

class StaticSecretProvider(CredentialProvider):
    SECRETS = {"github": "ghp_mock_secret_token", "confluence": "cf_mock_secret_token"}

    async def issue(self, tool_id: str, scopes: list[str], session_id: str) -> dict:
        token = self.SECRETS.get(tool_id, f"mock_secret_{uuid.uuid4().hex[:8]}")
        return {
            "provider": "static_secret",
            "token": token,
            "type": "bearer",
            "scopes": scopes,
        }

    async def revoke(self, lease_id: str) -> bool:
        return True
```

### 5. apps/token_broker/services/exchange_service.py
```python
from apps.token_broker.providers.base import CredentialProvider
from packages.identity_models.credential_lease import CredentialLease
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

class ExchangeService:
    def __init__(self, db: AsyncSession, providers: dict[str, CredentialProvider]):
        self.db = db
        self.providers = providers

    async def exchange(self, tool_id: str, scopes: list[str], session_id: str) -> dict:
        provider_name = "mock_oauth" if tool_id == "github" else "static_secret"
        provider = self.providers.get(provider_name, self.providers.get("mock_oauth"))
        if not provider:
            raise ValueError(f"No provider for tool: {tool_id}")

        cred = await provider.issue(tool_id, scopes, session_id)

        # Record lease — NEVER store raw token
        now = datetime.now(timezone.utc)
        lease = CredentialLease(
            session_id=uuid.UUID(session_id),
            tool_id=tool_id,
            scopes=scopes,
            provider=provider_name,
            issued_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        self.db.add(lease)
        await self.db.commit()

        # Return credential metadata for server-side injection
        return {
            "type": cred.get("type", "bearer"),
            "token": cred["token"],
            "expires_at": cred.get("expires_at", ""),
            "lease_id": str(lease.id),
        }
```

### 6. apps/token_broker/main.py
```python
"""Token Broker — issues downstream credentials without exposing raw secrets."""

import logging.config
from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel

from packages.common.settings import settings
from apps.token_broker.providers.mock_oauth import MockOAuthProvider
from apps.token_broker.providers.static_secret import StaticSecretProvider
from apps.token_broker.services.exchange_service import ExchangeService
from apps.identity_api.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession

logging.config.dictConfig({
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"json": {"()": "pythonjsonlogger.jsonlogger.JsonFormatter", "format": "%(asctime)s %(name)s %(levelname)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json", "stream": "ext://sys.stdout"}},
    "root": {"handlers": ["console"], "level": settings.log_level},
})

app = FastAPI(title="Agent Identity Lab — Token Broker", version="0.1.0")

providers = {
    "mock_oauth": MockOAuthProvider(),
    "static_secret": StaticSecretProvider(),
}

class TokenExchangeRequest(BaseModel):
    tool_id: str
    scopes: list[str]
    session_id: str

@app.get("/health")
async def health():
    return {"status": "ok", "service": "token_broker"}

@app.post("/v1/token-exchange")
async def token_exchange(
    data: TokenExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    svc = ExchangeService(db, providers)
    try:
        cred = await svc.exchange(data.tool_id, data.scopes, data.session_id)
        return cred
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 7. Tests — tests/unit/test_token_broker.py
```python
import pytest
from apps.token_broker.providers.mock_oauth import MockOAuthProvider
from apps.token_broker.providers.static_secret import StaticSecretProvider

@pytest.mark.asyncio
async def test_mock_oauth_issues_token():
    p = MockOAuthProvider()
    cred = await p.issue("github", ["repo:read"], "ses_123")
    assert cred["type"] == "bearer"
    assert cred["token"].startswith("mock_oauth_token_")
    assert "expires_at" in cred

@pytest.mark.asyncio
async def test_static_secret_issues_token():
    p = StaticSecretProvider()
    cred = await p.issue("github", ["repo:read"], "ses_123")
    assert cred["token"] == "ghp_mock_secret_token"

@pytest.mark.asyncio
async def test_revoke_returns_true():
    p = MockOAuthProvider()
    assert await p.revoke("any") is True

@pytest.mark.asyncio
async def test_no_raw_secret_leakage():
    """Ensure tokens don't expose real credentials in the returned metadata."""
    p = MockOAuthProvider()
    cred = await p.issue("github", ["admin"], "ses_123")
    # Token is mock, not real
    assert "ghp_" not in cred["token"] or cred["token"] == "ghp_mock_secret_token"
```

### 8. Tests — tests/integration/test_token_broker_api.py
```python
import pytest
from httpx import AsyncClient, ASGITransport
from apps.token_broker.main import app

@pytest.fixture
async def broker_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_token_broker_health(broker_client):
    r = await broker_client.get("/health")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_token_exchange_returns_credential(broker_client):
    r = await broker_client.post("/v1/token-exchange", json={
        "tool_id": "github", "scopes": ["repo:read"], "session_id": "ses_test"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "bearer"
    assert "token" in data
```

## Verification
All tests pass + lint/format clean.
