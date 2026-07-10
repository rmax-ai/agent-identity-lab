from typing import Any

import pytest

from packages.common.client import AgentIdentityClient


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeAsyncClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.closed = False

    async def post(self, url: str, json: dict[str, Any]) -> FakeResponse:
        self.calls.append(("POST", url, json))
        if url.endswith("/v1/sessions"):
            return FakeResponse({"id": "session-1", "token": "jwt-1"})
        return FakeResponse({"decision": "allow", "effective_scopes": ["repo:read"]})

    async def aclose(self) -> None:
        self.closed = True


def test_generate_keypair_returns_pems() -> None:
    sdk = AgentIdentityClient()

    private_pem, public_pem = sdk.generate_keypair()

    assert private_pem.startswith("-----BEGIN PRIVATE KEY-----")
    assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")


@pytest.mark.asyncio
async def test_create_session_signs_and_posts_payload() -> None:
    sdk = AgentIdentityClient()
    fake_client = FakeAsyncClient()
    sdk.client = fake_client  # ty: ignore[invalid-assignment]
    sdk.generate_keypair()

    response = await sdk.create_session(
        agent_id="agent-123",
        acting_user_id="user-123",
        requested_scopes=["repo:read"],
    )

    assert response["token"] == "jwt-1"
    method, url, payload = fake_client.calls[0]
    assert method == "POST"
    assert url.endswith("/v1/sessions")
    assert payload["agent_id"] == "agent-123"
    assert payload["runtime_attestation"]["agent_id"] == "agent-123"
    assert payload["runtime_attestation"]["signature"]


@pytest.mark.asyncio
async def test_authorize_posts_request() -> None:
    sdk = AgentIdentityClient()
    fake_client = FakeAsyncClient()
    sdk.client = fake_client  # ty: ignore[invalid-assignment]

    response = await sdk.authorize("jwt-1", "github", "search_code")

    assert response["decision"] == "allow"
    _, url, payload = fake_client.calls[0]
    assert url.endswith("/v1/authorize")
    assert payload == {
        "session_token": "jwt-1",
        "tool": "github",
        "operation": "search_code",
    }


@pytest.mark.asyncio
async def test_close_closes_underlying_client() -> None:
    sdk = AgentIdentityClient()
    fake_client = FakeAsyncClient()
    sdk.client = fake_client  # ty: ignore[invalid-assignment]

    await sdk.close()

    assert fake_client.closed is True
