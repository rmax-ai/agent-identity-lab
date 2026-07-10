import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from apps.token_broker.providers.base import CredentialProvider
from packages.identity_models.credential_lease import CredentialLease


class ExchangeService:
    def __init__(self, db: AsyncSession, providers: dict[str, CredentialProvider]):
        self.db = db
        self.providers = providers

    async def exchange(self, tool_id: str, scopes: list[str], session_id: str) -> dict[str, Any]:
        provider_name = self._select_provider(tool_id)
        provider = self.providers.get(provider_name)
        if provider is None:
            raise ValueError(f"No provider configured for {provider_name}")

        credential = await provider.issue(tool_id, scopes, session_id)

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=30)
        lease = CredentialLease(
            session_id=uuid.UUID(session_id),
            tool_id=tool_id,
            scopes=scopes,
            provider=provider_name,
            issued_at=now,
            expires_at=expires_at,
        )
        self.db.add(lease)
        await self.db.flush()

        return {
            "type": credential.get("type", "bearer"),
            "token": credential["token"],
            "expires_at": credential.get("expires_at", expires_at.isoformat()),
            "lease_id": str(lease.id),
        }

    @staticmethod
    def _select_provider(tool_id: str) -> str:
        if tool_id == "github":
            return "mock_oauth"
        return "static_secret"
