"""Initialize the local development database schema."""

import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from packages.common.models import Base
from packages.common.settings import settings

# Import models so SQLAlchemy metadata is fully registered before create_all().
import packages.attestation.models  # noqa: F401
import packages.audit.models  # noqa: F401
import packages.identity_models.agent  # noqa: F401
import packages.identity_models.blueprint  # noqa: F401
import packages.identity_models.credential_lease  # noqa: F401
import packages.identity_models.delegation  # noqa: F401
import packages.identity_models.session  # noqa: F401


async def main() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print(f"Initialized database schema at {settings.database_url}")


if __name__ == "__main__":
    asyncio.run(main())
