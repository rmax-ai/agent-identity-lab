"""Test fixtures for Agent Identity Lab."""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.identity_api.dependencies import get_db, get_settings, require_admin
from apps.identity_api.main import app
from packages.common.models import Base
from packages.common.settings import Settings

# Test database URL — use testcontainers in integration, SQLite in unit
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client with dependency overrides."""
    test_settings = Settings(
        database_url=TEST_DATABASE_URL,
        admin_api_key="test-admin-key",
        jwt_private_key_path="",
        jwt_public_key_path="",
    )

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[require_admin] = lambda: "test-admin-key"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
