import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_agent(client: AsyncClient):
    blueprint_response = await client.post(
        "/v1/blueprints",
        json={"slug": "agent-bp", "name": "Agent BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    blueprint_id = blueprint_response.json()["id"]
    await client.post(
        f"/v1/blueprints/{blueprint_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    response = await client.post(
        "/v1/agents",
        json={"blueprint_id": blueprint_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["owner_id"] == "usr_test"
    assert data["status"] == "draft"
    assert data["principal_uri"].startswith("agent://local/")


@pytest.mark.asyncio
async def test_activate_agent(client: AsyncClient):
    blueprint_response = await client.post(
        "/v1/blueprints",
        json={"slug": "act-agent-bp", "name": "Act Agent BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    blueprint_id = blueprint_response.json()["id"]
    await client.post(
        f"/v1/blueprints/{blueprint_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    agent_response = await client.post(
        "/v1/agents",
        json={"blueprint_id": blueprint_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_response.json()["id"]

    activation = await client.post(
        f"/v1/agents/{agent_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert activation.status_code == 200

    verify = await client.get(f"/v1/agents/{agent_id}")
    assert verify.json()["status"] == "active"
    assert verify.json()["activated_at"] is not None


@pytest.mark.asyncio
async def test_suspend_agent(client: AsyncClient):
    blueprint_response = await client.post(
        "/v1/blueprints",
        json={"slug": "susp-bp", "name": "Suspension BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    blueprint_id = blueprint_response.json()["id"]
    await client.post(
        f"/v1/blueprints/{blueprint_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    agent_response = await client.post(
        "/v1/agents",
        json={"blueprint_id": blueprint_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_response.json()["id"]
    await client.post(
        f"/v1/agents/{agent_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    suspend = await client.post(
        f"/v1/agents/{agent_id}/suspend",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert suspend.status_code == 200

    verify = await client.get(f"/v1/agents/{agent_id}")
    assert verify.json()["status"] == "suspended"


@pytest.mark.asyncio
async def test_revoke_agent(client: AsyncClient):
    blueprint_response = await client.post(
        "/v1/blueprints",
        json={"slug": "revoke-bp", "name": "Revoke BP"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    blueprint_id = blueprint_response.json()["id"]
    await client.post(
        f"/v1/blueprints/{blueprint_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    agent_response = await client.post(
        "/v1/agents",
        json={"blueprint_id": blueprint_id, "owner_id": "usr_test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    agent_id = agent_response.json()["id"]

    response = await client.post(
        f"/v1/agents/{agent_id}/revoke",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"
