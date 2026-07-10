import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_blueprint(client: AsyncClient):
    response = await client.post(
        "/v1/blueprints",
        json={"slug": "test-bp", "name": "Test Blueprint"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "test-bp"
    assert data["status"] == "draft"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_blueprints(client: AsyncClient):
    await client.post(
        "/v1/blueprints",
        json={"slug": "list-test", "name": "List Test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    response = await client.get("/v1/blueprints")
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_get_blueprint_not_found(client: AsyncClient):
    response = await client.get("/v1/blueprints/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_activate_blueprint(client: AsyncClient):
    response = await client.post(
        "/v1/blueprints",
        json={"slug": "activate-test", "name": "Activate Test"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    blueprint_id = response.json()["id"]

    activation = await client.post(
        f"/v1/blueprints/{blueprint_id}/activate",
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert activation.status_code == 200

    verify = await client.get(f"/v1/blueprints/{blueprint_id}")
    assert verify.json()["status"] == "active"


@pytest.mark.asyncio
async def test_create_duplicate_slug(client: AsyncClient):
    await client.post(
        "/v1/blueprints",
        json={"slug": "dup-test", "name": "First"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )

    response = await client.post(
        "/v1/blueprints",
        json={"slug": "dup-test", "name": "Second"},
        headers={"X-Admin-API-Key": "test-admin-key"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_requires_admin_key(client: AsyncClient):
    response = await client.post(
        "/v1/blueprints",
        json={"slug": "no-auth", "name": "No Auth"},
    )
    assert response.status_code == 401
