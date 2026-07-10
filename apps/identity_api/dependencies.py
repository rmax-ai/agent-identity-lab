"""FastAPI dependencies for database, auth, and settings."""

from collections.abc import AsyncGenerator

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.common.settings import Settings, settings

api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)


async def get_settings() -> Settings:
    return settings


def create_engine(database_url: str | None = None):
    url = database_url or settings.database_url
    return create_async_engine(url, echo=False, pool_size=5, max_overflow=10)


_engine = create_engine()
_async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def require_admin(api_key: str | None = Security(api_key_header)) -> str:
    """Validate admin API key. Returns the key if valid, raises 401 otherwise."""
    if not api_key or api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
