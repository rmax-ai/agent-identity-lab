"""Demo: Invalid runtime environment is denied during authorization."""

import asyncio

from examples._support import create_blueprint_and_agent


async def demo() -> None:
    sdk, _blueprint, agent = await create_blueprint_and_agent(
        slug_prefix="demo-invalid-runtime",
        blueprint_name="Demo Runtime Guardrails",
        max_scopes=["repo:read"],
        approved_environments=["production"],
    )
    try:
        session = await sdk.create_session(
            agent_id=agent["id"],
            acting_user_id="demo_user",
            requested_scopes=["repo:read"],
            environment="development",
        )
        auth = await sdk.authorize(session["token"], "github", "search_code")
        print(f"Demo: Invalid Runtime — decision={auth['decision']}, reason={auth['reason']}")
        assert auth["decision"] == "deny", "Expected authorization deny for invalid runtime"
        print("PASS: invalid runtime environment was denied")
    finally:
        await sdk.close()


if __name__ == "__main__":
    asyncio.run(demo())
