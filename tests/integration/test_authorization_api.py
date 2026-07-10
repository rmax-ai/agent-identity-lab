"""Integration tests for the /v1/authorize endpoint."""

import uuid
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient

from packages.attestation.verifier import AttestationVerifier


def make_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return private_pem, public_pem


async def setup_agent_with_session(
    client: AsyncClient,
    slug: str,
    scopes: list[str],
) -> str:
    """Create a blueprint, agent, and session, then return the session token."""
    private_pem, public_pem = make_keypair()

    bp_response = await client.post(
        "/v1/blueprints",
        json={
            "slug": slug,
            "name": slug,
            "max_scopes": scopes,
            "approved_environments": ["development"],
        },
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_response.json()["id"]
    await client.post(
        f"/v1/blueprints/{bp_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    agent_response = await client.post(
        "/v1/agents",
        json={
            "blueprint_id": bp_id,
            "owner_id": "usr_test",
            "public_key": public_pem,
        },
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_response.json()["id"]
    await client.post(
        f"/v1/agents/{agent_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    claims = {
        "agent_id": agent_id,
        "container_digest": "sha256:abc",
        "git_commit": "abc123",
        "environment": "development",
        "host_id": "docker-01",
        "framework": "hermes",
        "framework_version": "0.4.0",
        "model": "deepseek-chat",
        "prompt_version": "v1",
        "issued_at": datetime.now(UTC).isoformat(),
        "nonce": str(uuid.uuid4()),
    }
    signature = AttestationVerifier.sign_attestation(claims, private_pem)

    session_response = await client.post(
        "/v1/sessions",
        json={
            "agent_id": agent_id,
            "acting_user_id": "usr_test",
            "requested_scopes": scopes,
            "model_id": "deepseek-chat",
            "runtime_attestation": {**claims, "signature": signature},
        },
    )
    return session_response.json()["token"]


@pytest.mark.asyncio
async def test_authorize_allowed_read(client: AsyncClient):
    token = await setup_agent_with_session(client, "auth-test-bp", ["repo:read"])
    response = await client.post(
        "/v1/authorize",
        json={
            "session_token": token,
            "tool": "github",
            "operation": "search_code",
            "resource": {"repository": "rmax-ai/example"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "allow"
    assert "repo:read" in data["effective_scopes"]


@pytest.mark.asyncio
async def test_authorize_denied_write_for_research(client: AsyncClient):
    token = await setup_agent_with_session(client, "research-agent", ["issues:write"])
    response = await client.post(
        "/v1/authorize",
        json={
            "session_token": token,
            "tool": "github",
            "operation": "create_issue",
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "deny"


@pytest.mark.asyncio
async def test_authorize_invalid_token(client: AsyncClient):
    response = await client.post(
        "/v1/authorize",
        json={
            "session_token": "not.a.valid.token",
            "tool": "github",
            "operation": "search_code",
        },
    )
    assert response.status_code == 401
