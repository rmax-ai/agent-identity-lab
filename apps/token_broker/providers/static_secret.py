import uuid
from typing import Any, ClassVar

from apps.token_broker.providers.base import CredentialProvider


class StaticSecretProvider(CredentialProvider):
    SECRETS: ClassVar[dict[str, str]] = {
        "github": "ghp_mock_secret_token",
        "confluence": "cf_mock_secret_token",
    }

    async def issue(
        self,
        tool_id: str,
        scopes: list[str],
        session_id: str,
    ) -> dict[str, Any]:
        token = self.SECRETS.get(tool_id, f"mock_secret_{uuid.uuid4().hex[:8]}")
        return {
            "provider": "static_secret",
            "token": token,
            "type": "bearer",
            "scopes": scopes,
        }

    async def revoke(self, lease_id: str) -> bool:
        return True
