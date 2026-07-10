"""Demo: Write attempt denied for a read-only research workflow."""

import asyncio

from examples._support import create_blueprint_and_agent


async def demo() -> None:
    sdk, _blueprint, agent = await create_blueprint_and_agent(
        slug_prefix="research-agent",
        blueprint_name="Research Agent",
        max_scopes=["repo:read", "issues:read"],
    )
    try:
        session = await sdk.create_session(
            agent_id=agent["id"],
            acting_user_id="demo_user",
            requested_scopes=["issues:write"],
        )
        auth = await sdk.authorize(session["token"], "github", "create_issue")
        print(f"Demo: Denied Write — decision={auth['decision']}, reason={auth['reason']}")
        assert auth["decision"] == "deny", "Expected authorization deny"
        print("PASS: unauthorized write attempt was denied")
    finally:
        await sdk.close()


if __name__ == "__main__":
    asyncio.run(demo())
