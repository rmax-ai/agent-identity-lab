from abc import ABC, abstractmethod
from typing import Any


class CredentialProvider(ABC):
    @abstractmethod
    async def issue(
        self,
        tool_id: str,
        scopes: list[str],
        session_id: str,
    ) -> dict[str, Any]:
        """Issue a downstream credential."""

    @abstractmethod
    async def revoke(self, lease_id: str) -> bool:
        """Revoke a previously issued credential lease."""
