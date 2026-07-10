"""Happy-path session creation integration test."""

import uuid
from datetime import UTC, datetime

import jwt as jwt_lib
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


@pytest.mark.asyncio
async def test_full_session_creation_flow(client: AsyncClient):
    """End-to-end: blueprint → agent → attestation → session token."""
    private_pem, public_pem = make_keypair()

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
        "issued_at": datetime.now(UTC).isoformat(),
        "nonce": str(uuid.uuid4()),
    }
    signature = AttestationVerifier.sign_attestation(claims, private_pem)

    response = await client.post(
        "/v1/sessions",
        json={
            "agent_id": agent_id,
            "acting_user_id": "usr_test",
            "requested_scopes": ["repo:read"],
            "requested_ttl_seconds": 900,
            "model_id": "deepseek-chat",
            "prompt_version": "research-v3",
            "runtime_attestation": {**claims, "signature": signature},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "token" in data
    assert data["effective_scopes"] == ["repo:read"]
    assert data["acting_user_id"] == "usr_test"
    assert "trace_id" in data

    token_claims = jwt_lib.decode(data["token"], options={"verify_signature": False})
    assert token_claims["agent_id"] == agent_id
    assert token_claims["scopes"] == ["repo:read"]
    assert token_claims["acting_user"] == "usr_test"


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
    await client.post(
        f"/v1/blueprints/{bp_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test", "public_key": public_pem},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]
    await client.post(
        f"/v1/agents/{agent_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

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
        "issued_at": datetime.now(UTC).isoformat(),
        "nonce": str(uuid.uuid4()),
    }
    signature = AttestationVerifier.sign_attestation(claims, private_pem)

    response = await client.post(
        "/v1/sessions",
        json={
            "agent_id": agent_id,
            "acting_user_id": "usr_test",
            "requested_scopes": ["repo:read"],
            "model_id": "deepseek-chat",
            "runtime_attestation": {**claims, "signature": signature},
        },
    )
    assert response.status_code == 201
    session_id = response.json()["id"]

    revoke_response = await client.post(f"/v1/sessions/{session_id}/revoke")
    assert revoke_response.status_code == 200

    verify_response = await client.get(f"/v1/sessions/{session_id}")
    assert verify_response.json()["status"] == "revoked"
