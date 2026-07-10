"""Demo: Suspended agents can no longer create new sessions."""

import asyncio

import httpx

from examples._support import create_blueprint_and_agent, suspend_agent


async def demo() -> None:
    sdk, _blueprint, agent = await create_blueprint_and_agent(
        slug_prefix="demo-suspended",
        blueprint_name="Demo Suspended Agent",
        max_scopes=["repo:read"],
    )
    try:
        first_session = await sdk.create_session(
            agent_id=agent["id"],
            acting_user_id="demo_user",
            requested_scopes=["repo:read"],
        )
        print(f"Created initial session {first_session['id']}")

        suspension = await suspend_agent(agent["id"])
        print(f"Suspended agent {suspension['id']}")

        try:
            await sdk.create_session(
                agent_id=agent["id"],
                acting_user_id="demo_user",
                requested_scopes=["repo:read"],
            )
        except httpx.HTTPStatusError as exc:
            assert exc.response.status_code == 400
            print(f"PASS: suspended agent session creation failed with {exc.response.status_code}")
            return

        raise AssertionError("Expected session creation to fail after agent suspension")
    finally:
        await sdk.close()


if __name__ == "__main__":
    asyncio.run(demo())
