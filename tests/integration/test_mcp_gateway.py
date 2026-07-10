"""Integration tests for the MCP Gateway."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.mcp_gateway.main import create_app
from apps.mcp_gateway.middleware.auth import GatewayAuth
from apps.mcp_gateway.proxy.forwarder import MCPForwarder
from apps.mock_mcp_server.main import app as mock_app
from packages.common.settings import Settings
from packages.token_library.keys import load_private_key


def make_session_token(
    settings: Settings,
    scopes: list[str],
    trace_id: str = "trace-test",
) -> str:
    """Create a valid session token for gateway tests."""
    now = datetime.now(UTC)
    claims = {
        "iss": settings.jwt_issuer,
        "sub": "agent:test-agent",
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "jti": str(uuid.uuid4()),
        "agent_id": "test-agent",
        "scopes": scopes,
        "trace_id": trace_id,
    }
    return jwt.encode(
        claims,
        load_private_key(settings),
        algorithm=settings.jwt_algorithm,
    )


def build_auth_app(
    decision: str = "allow",
    reason: str = "Permission intersection satisfied",
) -> FastAPI:
    """Build a stub authorization service."""
    auth_app = FastAPI()

    @auth_app.post("/v1/authorize")
    async def authorize(payload: dict) -> dict:
        if not payload.get("session_token"):
            return {"decision": "deny", "effective_scopes": [], "reason": "Missing session token"}
        return {
            "decision": decision,
            "effective_scopes": ["repo:read"] if decision == "allow" else [],
            "reason": reason,
            "decision_id": "dec_test",
            "obligations": ["log_request"] if decision == "allow" else [],
        }

    return auth_app


def build_gateway_app(
    auth_app: FastAPI | None = None,
    settings: Settings | None = None,
):
    """Build a gateway app wired to stub auth and mock MCP services."""
    test_settings = settings or Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        admin_api_key="test-admin-key",
        jwt_private_key_path="",
        jwt_public_key_path="",
    )
    gateway_app = create_app(test_settings)
    identity_transport = ASGITransport(app=auth_app or build_auth_app())
    mock_transport = ASGITransport(app=mock_app)
    gateway_app.state.auth = GatewayAuth(
        test_settings,
        client=AsyncClient(transport=identity_transport, base_url="http://identity"),
    )
    gateway_app.state.forwarder = MCPForwarder(
        mcp_server_url="http://mock",
        client=AsyncClient(transport=mock_transport, base_url="http://mock"),
    )
    return gateway_app, test_settings


@pytest.mark.asyncio
async def test_gateway_health() -> None:
    gateway_app, _settings = build_gateway_app()
    transport = ASGITransport(app=gateway_app)

    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "mcp_gateway"


@pytest.mark.asyncio
async def test_gateway_rejects_no_token() -> None:
    gateway_app, _settings = build_gateway_app()
    transport = ASGITransport(app=gateway_app)

    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.get("/mcp/tools/github.search_code")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_gateway_rejects_invalid_token() -> None:
    gateway_app, _settings = build_gateway_app()
    transport = ASGITransport(app=gateway_app)

    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.get(
            "/mcp/tools/github.search_code",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_gateway_allows_and_forwards_request() -> None:
    gateway_app, settings = build_gateway_app()
    transport = ASGITransport(app=gateway_app)
    token = make_session_token(settings, ["repo:read"])

    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.get(
            "/mcp/tools/github.search_code",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Agent-Trace-ID": "trace-test-123",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["tool"] == "github"
    assert data["operation"] == "search_code"
    assert data["trace_id"] == "trace-test-123"


@pytest.mark.asyncio
async def test_gateway_denies_unknown_tool() -> None:
    gateway_app, settings = build_gateway_app()
    transport = ASGITransport(app=gateway_app)
    token = make_session_token(settings, ["repo:read"])

    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.get(
            "/mcp/tools/evil.destroy",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    assert "Unknown tool or operation" in response.json()["detail"]


@pytest.mark.asyncio
async def test_gateway_denies_policy_rejected_request() -> None:
    auth_app = build_auth_app(
        decision="deny",
        reason="Research agents cannot perform write operations",
    )
    gateway_app, settings = build_gateway_app(auth_app=auth_app)
    transport = ASGITransport(app=gateway_app)
    token = make_session_token(settings, ["issues:write"])

    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.post(
            "/mcp/tools/github.create_issue",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "Denied"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Research agents cannot perform write operations"


@pytest.mark.asyncio
async def test_mock_mcp_health() -> None:
    transport = ASGITransport(app=mock_app)
    async with AsyncClient(transport=transport, base_url="http://mock") as client:
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_mock_mcp_github() -> None:
    transport = ASGITransport(app=mock_app)
    async with AsyncClient(transport=transport, base_url="http://mock") as client:
        response = await client.get("/github/search_code")
        assert response.status_code == 200
        data = response.json()
        assert data["tool"] == "github"
        assert data["operation"] == "search_code"
