"""Auth middleware for the MCP Gateway."""

from typing import Any

import httpx
from fastapi import HTTPException, Request, status

from apps.mcp_gateway.tool_registry.registry import get_required_scopes
from packages.common.settings import Settings
from packages.token_library.validator import validate_session_token


class GatewayAuth:
    """Validate gateway bearer tokens and delegate policy checks."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.identity_api_url = settings.identity_api_url.rstrip("/")
        self.client = client

    async def authenticate(self, request: Request) -> dict[str, Any]:
        """Validate the session token and return claims plus the original token."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
            )

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            claims = validate_session_token(token, self.settings)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc

        claims["_raw_token"] = token
        return claims

    async def authorize(
        self,
        claims: dict[str, Any],
        tool_id: str,
        operation: str,
    ) -> dict[str, Any]:
        """Call the identity API to authorize tool access."""
        required_scopes = get_required_scopes(tool_id, operation)
        if required_scopes is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unknown tool or operation: {tool_id}.{operation}",
            )

        try:
            client = self.client or httpx.AsyncClient(timeout=10.0)
            self.client = client
            response = await client.post(
                f"{self.identity_api_url}/v1/authorize",
                json={
                    "session_token": claims["_raw_token"],
                    "tool": tool_id,
                    "operation": operation,
                },
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Authorization service error: {exc}",
            ) from exc

        if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Authorization service error",
            )
        if response.status_code >= status.HTTP_400_BAD_REQUEST:
            detail: Any
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=detail)

        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self.client is not None:
            await self.client.aclose()
