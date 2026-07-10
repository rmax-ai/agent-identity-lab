"""Shared helpers for Phase 7 demos."""

import uuid
from typing import Any

import httpx

from packages.common.client import AgentIdentityClient

ADMIN_HEADERS = {"X-Admin-API-Key": "test-admin-key"}
IDENTITY_API_URL = "http://localhost:8000"
TOKEN_BROKER_URL = "http://localhost:8001"


async def create_blueprint(
    client: httpx.AsyncClient,
    *,
    slug: str,
    name: str,
    max_scopes: list[str],
    approved_environments: list[str] | None = None,
    approved_models: list[str] | None = None,
) -> dict[str, Any]:
    response = await client.post(
        f"{IDENTITY_API_URL}/v1/blueprints",
        json={
            "slug": slug,
            "name": name,
            "max_scopes": max_scopes,
            "approved_environments": approved_environments or ["development"],
            "approved_models": approved_models or ["deepseek-chat"],
        },
        headers=ADMIN_HEADERS,
    )
    response.raise_for_status()
    blueprint = response.json()
    activate = await client.post(
        f"{IDENTITY_API_URL}/v1/blueprints/{blueprint['id']}/activate",
        headers=ADMIN_HEADERS,
    )
    activate.raise_for_status()
    return blueprint


async def create_agent(
    client: httpx.AsyncClient,
    *,
    blueprint_id: str,
    owner_id: str,
    public_key: str,
) -> dict[str, Any]:
    response = await client.post(
        f"{IDENTITY_API_URL}/v1/agents",
        json={
            "blueprint_id": blueprint_id,
            "owner_id": owner_id,
            "public_key": public_key,
        },
        headers=ADMIN_HEADERS,
    )
    response.raise_for_status()
    agent = response.json()
    activate = await client.post(
        f"{IDENTITY_API_URL}/v1/agents/{agent['id']}/activate",
        headers=ADMIN_HEADERS,
    )
    activate.raise_for_status()
    return agent


async def create_blueprint_and_agent(
    *,
    slug_prefix: str,
    blueprint_name: str,
    max_scopes: list[str],
    approved_environments: list[str] | None = None,
    owner_id: str = "demo_user",
) -> tuple[AgentIdentityClient, dict[str, Any], dict[str, Any]]:
    sdk = AgentIdentityClient(IDENTITY_API_URL)
    _, public_key = sdk.generate_keypair()
    unique_slug = f"{slug_prefix}-{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        blueprint = await create_blueprint(
            client,
            slug=unique_slug,
            name=blueprint_name,
            max_scopes=max_scopes,
            approved_environments=approved_environments,
        )
        agent = await create_agent(
            client,
            blueprint_id=blueprint["id"],
            owner_id=owner_id,
            public_key=public_key,
        )

    return sdk, blueprint, agent


async def suspend_agent(agent_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{IDENTITY_API_URL}/v1/agents/{agent_id}/suspend",
            headers=ADMIN_HEADERS,
        )
        response.raise_for_status()
        return response.json()


async def exchange_token(*, tool_id: str, scopes: list[str], session_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{TOKEN_BROKER_URL}/v1/token-exchange",
            json={
                "tool_id": tool_id,
                "scopes": scopes,
                "session_id": session_id,
            },
        )
        response.raise_for_status()
        return response.json()
