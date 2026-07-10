"""Demo: Downstream credentials are leased without exposing static secrets."""

import asyncio

from examples._support import create_blueprint_and_agent, exchange_token


async def demo() -> None:
    sdk, _blueprint, agent = await create_blueprint_and_agent(
        slug_prefix="demo-secret-isolation",
        blueprint_name="Demo Secret Isolation Agent",
        max_scopes=["repo:read"],
    )
    try:
        session = await sdk.create_session(
            agent_id=agent["id"],
            acting_user_id="demo_user",
            requested_scopes=["repo:read"],
        )
        credential = await exchange_token(
            tool_id="github",
            scopes=["repo:read"],
            session_id=session["id"],
        )
        print(
            f"Demo: Secret Isolation — type={credential['type']}, lease_id={credential['lease_id']}"
        )
        assert credential["token"].startswith("mock_oauth_token_"), (
            "Expected an ephemeral downstream token, not a static provider secret"
        )
        assert "ghp_mock_secret_token" not in credential["token"]
        assert "raw_secret" not in credential
        assert "refresh_token" not in credential
        print("PASS: token broker returned a leased credential without raw secret material")
    finally:
        await sdk.close()


if __name__ == "__main__":
    asyncio.run(demo())
