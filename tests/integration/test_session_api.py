"""Integration tests for session API endpoints."""

import uuid

import pytest
from httpx import AsyncClient


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

    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]

    response = await client.post(
        "/v1/sessions",
        json={
            "agent_id": agent_id,
            "acting_user_id": "usr_test",
            "requested_scopes": ["repo:read"],
            "model_id": "deepseek-chat",
            "runtime_attestation": {"signature": "00" * 64},
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_session_requires_agent_exists(client: AsyncClient):
    response = await client.post(
        "/v1/sessions",
        json={
            "agent_id": str(uuid.uuid4()),
            "model_id": "deepseek-chat",
            "runtime_attestation": {"signature": "00" * 64},
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_session_not_found(client: AsyncClient):
    response = await client.get(f"/v1/sessions/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_delegation(client: AsyncClient):
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "deleg-bp", "name": "Deleg BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(
        f"/v1/blueprints/{bp_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]

    response = await client.post(
        "/v1/delegations",
        json={
            "user_id": "usr_test",
            "agent_id": agent_id,
            "scopes": ["repo:read"],
            "ttl_seconds": 1800,
        },
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert response.status_code == 201
    assert "id" in response.json()


@pytest.mark.asyncio
async def test_revoke_delegation(client: AsyncClient):
    bp_r = await client.post(
        "/v1/blueprints",
        json={"slug": "del-rev-bp", "name": "Del Rev BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    bp_id = bp_r.json()["id"]
    await client.post(
        f"/v1/blueprints/{bp_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    agent_r = await client.post(
        "/v1/agents",
        json={"blueprint_id": bp_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_r.json()["id"]

    delegation_r = await client.post(
        "/v1/delegations",
        json={"user_id": "usr_test", "agent_id": agent_id, "scopes": ["repo:read"]},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    delegation_id = delegation_r.json()["id"]

    revoke_response = await client.post(
        f"/v1/delegations/{delegation_id}/revoke",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert revoke_response.status_code == 200

    verify_response = await client.get(f"/v1/delegations/{delegation_id}")
    assert verify_response.json()["revoked"] is True
