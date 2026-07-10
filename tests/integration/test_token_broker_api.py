import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from apps.identity_api.dependencies import get_db
from apps.token_broker.main import app


class FakeAsyncSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def flush(self) -> None:
        return None


@pytest_asyncio.fixture
async def broker_client() -> AsyncGenerator[AsyncClient, None]:
    fake_session = FakeAsyncSession()
    app.dependency_overrides[get_db] = lambda: fake_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_token_broker_health(broker_client: AsyncClient):
    response = await broker_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "token_broker"}


@pytest.mark.asyncio
async def test_token_exchange_returns_credential(broker_client: AsyncClient):
    response = await broker_client.post(
        "/v1/token-exchange",
        json={
            "tool_id": "github",
            "scopes": ["repo:read"],
            "session_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "bearer"
    assert data["token"].startswith("mock_oauth_token_")
    assert data["lease_id"]
