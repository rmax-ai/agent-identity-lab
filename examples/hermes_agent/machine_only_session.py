"""Demo: Machine-only Hermes session without an acting user."""

import asyncio

from examples._support import create_blueprint_and_agent


async def demo() -> None:
    sdk, _blueprint, agent = await create_blueprint_and_agent(
        slug_prefix="demo-machine-only",
        blueprint_name="Demo Machine-Only Agent",
        max_scopes=["repo:read"],
    )
    try:
        session = await sdk.create_session(
            agent_id=agent["id"],
            acting_user_id=None,
            requested_scopes=["repo:read"],
        )
        auth = await sdk.authorize(session["token"], "github", "search_code")
        print(
            "Demo: Machine-Only Session — "
            f"decision={auth['decision']}, acting_user={session['acting_user_id']}"
        )
        assert session["acting_user_id"] is None
        assert auth["decision"] == "allow"
        print("PASS: machine-only session authorized successfully")
    finally:
        await sdk.close()


if __name__ == "__main__":
    asyncio.run(demo())
