"""Demo: Authorized read access for a delegated research agent."""

import asyncio

from examples._support import create_blueprint_and_agent


async def demo() -> None:
    sdk, _blueprint, agent = await create_blueprint_and_agent(
        slug_prefix="demo-research",
        blueprint_name="Demo Research Agent",
        max_scopes=["repo:read", "issues:read"],
    )
    try:
        session = await sdk.create_session(
            agent_id=agent["id"],
            acting_user_id="demo_user",
            requested_scopes=["repo:read"],
            model_id="deepseek-chat",
            prompt_version="v1",
        )
        auth = await sdk.authorize(session["token"], "github", "search_code")
        print(
            "Demo: Authorized Read — "
            f"decision={auth['decision']}, scopes={auth['effective_scopes']}"
        )
        assert auth["decision"] == "allow", "Expected authorization allow"
        print("PASS: authorized read succeeded")
    finally:
        await sdk.close()


if __name__ == "__main__":
    asyncio.run(demo())
