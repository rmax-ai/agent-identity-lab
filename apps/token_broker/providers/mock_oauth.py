import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from apps.token_broker.providers.base import CredentialProvider


class MockOAuthProvider(CredentialProvider):
    async def issue(
        self,
        tool_id: str,
        scopes: list[str],
        session_id: str,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        return {
            "provider": "mock_oauth",
            "token": f"mock_oauth_token_{uuid.uuid4().hex[:16]}",
            "type": "bearer",
            "scopes": scopes,
            "expires_at": (now + timedelta(minutes=30)).isoformat(),
        }

    async def revoke(self, lease_id: str) -> bool:
        return True
