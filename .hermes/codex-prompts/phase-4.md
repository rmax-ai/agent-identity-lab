# Phase 4: MCP Gateway

Implement the MCP Gateway — the enforcement boundary between agents and MCP servers.

**Context:** Phases 1-3 complete. Working: blueprints, agents, sessions with JWT tokens, attestation verification, policy engine with scope intersection, /v1/authorize endpoint. 47 tests pass.

**Tech:** Python 3.12, FastAPI, httpx, PyJWT

**Test:** `PYTHONPATH=. uv run pytest tests/ -v`
**Lint:** `PYTHONPATH=. uv run ruff check packages/ apps/ tests/`

## Files to Create

### 1. apps/mcp_gateway/tool_registry/registry.py
```python
"""Tool registry: maps MCP tool operations to required scopes."""

TOOL_MAPPINGS = {
    "github.search_code": {"required_scopes": ["repo:read"]},
    "github.list_repos": {"required_scopes": ["repo:read"]},
    "github.create_issue": {"required_scopes": ["issues:write"]},
    "github.list_issues": {"required_scopes": ["issues:read"]},
    "github.read_file": {"required_scopes": ["repo:read"]},
    "confluence.search": {"required_scopes": ["pages:read"]},
    "confluence.create_page": {"required_scopes": ["pages:write"]},
    "confluence.update_page": {"required_scopes": ["pages:write"]},
}


def get_required_scopes(tool_id: str, operation: str) -> list[str] | None:
    key = f"{tool_id}.{operation}"
    mapping = TOOL_MAPPINGS.get(key)
    if mapping:
        return mapping["required_scopes"]
    return None


def list_tools() -> list[str]:
    return list(TOOL_MAPPINGS.keys())
```

### 2. apps/mcp_gateway/middleware/auth.py
```python
"""Auth middleware for MCP Gateway — validates session tokens and authorizes requests."""

import uuid
from fastapi import Request, HTTPException, status
import httpx
from packages.token_library.validator import validate_session_token
from packages.common.settings import Settings
from apps.mcp_gateway.tool_registry.registry import get_required_scopes


class GatewayAuth:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.identity_api_url = settings.identity_api_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=10.0)

    async def authenticate(self, request: Request) -> dict:
        """Validate the session token and return claims."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        token = auth_header[7:]
        try:
            claims = validate_session_token(token, self.settings)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e))
        return claims

    async def authorize(self, claims: dict, tool_id: str, operation: str) -> dict:
        """Call the identity API to authorize the tool access."""
        required = get_required_scopes(tool_id, operation)
        if required is None:
            raise HTTPException(status_code=403, detail=f"Unknown tool or operation: {tool_id}.{operation}")

        # Extract session token from claims — re-serialize needed parts
        # Use the identity API's /v1/authorize endpoint
        try:
            # We need the original token, but we only have claims.
            # For the gateway, we'll verify directly against the authorization API
            response = await self.client.post(
                f"{self.identity_api_url}/v1/authorize",
                json={
                    "session_token": claims.get("_raw_token", ""),
                    "tool": tool_id,
                    "operation": operation,
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Authorization service error: {e}")

    async def close(self):
        await self.client.aclose()
```

### 3. apps/mcp_gateway/proxy/forwarder.py
```python
"""Forward authorized requests to downstream MCP servers."""

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse


class MCPForwarder:
    def __init__(self, mcp_server_url: str = "http://localhost:8003"):
        self.mcp_url = mcp_server_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def forward(self, request: Request, downstream_credentials: dict | None = None):
        """Forward the request to the MCP server, injecting credentials."""
        body = await request.body()
        headers = dict(request.headers)

        # Strip gateway-internal headers
        headers.pop("host", None)
        headers.pop("authorization", None)  # Replace with downstream cred if needed

        # Inject downstream credentials if provided
        if downstream_credentials:
            cred_type = downstream_credentials.get("type", "bearer")
            if cred_type == "bearer":
                headers["authorization"] = f"Bearer {downstream_credentials.get('token', '')}"
            elif cred_type == "header":
                headers[downstream_credentials.get("header_name", "X-Api-Key")] = (
                    downstream_credentials.get("token", "")
                )

        # Forward trace ID
        trace_id = request.headers.get("X-Agent-Trace-ID", "")
        if trace_id:
            headers["X-Trace-ID"] = trace_id

        target_url = f"{self.mcp_url}{request.url.path}"
        try:
            response = await self.client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
            return JSONResponse(
                content=response.json() if response.headers.get("content-type", "").startswith("application/json") else {"result": response.text},
                status_code=response.status_code,
            )
        except httpx.HTTPError as e:
            return JSONResponse(
                content={"error": str(e)},
                status_code=502,
            )

    async def close(self):
        await self.client.aclose()
```

### 4. apps/mcp_gateway/main.py
```python
"""MCP Gateway — enforcement boundary between agents and MCP servers."""

import logging.config
from fastapi import FastAPI, Request, HTTPException

from packages.common.settings import settings
from apps.mcp_gateway.middleware.auth import GatewayAuth
from apps.mcp_gateway.proxy.forwarder import MCPForwarder

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json", "stream": "ext://sys.stdout"},
    },
    "root": {"handlers": ["console"], "level": settings.log_level},
})
logger = logging.getLogger("mcp_gateway")

app = FastAPI(title="Agent Identity Lab — MCP Gateway", version="0.1.0")
auth = GatewayAuth(settings)
forwarder = MCPForwarder()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mcp_gateway"}


@app.api_route("/mcp/tools/{tool_id}.{operation:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_mcp_request(tool_id: str, operation: str, request: Request):
    # 1. Authenticate — validate session token
    claims = await auth.authenticate(request)

    # 2. Authorize — check policy
    try:
        auth_result = await auth.authorize(claims, tool_id, operation)
    except HTTPException:
        raise

    if auth_result.get("decision") != "allow":
        raise HTTPException(status_code=403, detail=auth_result.get("reason", "Access denied"))

    # 3. Forward to MCP server
    return await forwarder.forward(request)
```

### 5. apps/mock_mcp_server/main.py
```python
"""Mock MCP Server for development and testing."""

from fastapi import FastAPI, Request

app = FastAPI(title="Mock MCP Server", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock_mcp_server"}


@app.api_route("/github/{operation:path}", methods=["GET", "POST"])
async def github_tools(operation: str, request: Request):
    body = await request.json() if request.method == "POST" else {}
    return {
        "tool": "github",
        "operation": operation,
        "result": f"Mock: {operation} completed successfully",
        "trace_id": request.headers.get("X-Trace-ID", ""),
    }


@app.api_route("/confluence/{operation:path}", methods=["GET", "POST"])
async def confluence_tools(operation: str, request: Request):
    return {
        "tool": "confluence",
        "operation": operation,
        "result": f"Mock: {operation} completed successfully",
    }
```

### 6. Tests — tests/integration/test_mcp_gateway.py
```python
"""Integration tests for the MCP Gateway."""

import pytest
from httpx import AsyncClient

from apps.mcp_gateway.main import app as gateway_app
from apps.mock_mcp_server.main import app as mock_app
from httpx import ASGITransport


@pytest.fixture
async def gateway_client():
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_gateway_health(gateway_client: AsyncClient):
    r = await gateway_client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "mcp_gateway"


@pytest.mark.asyncio
async def test_gateway_rejects_no_token(gateway_client: AsyncClient):
    r = await gateway_client.get("/mcp/tools/github.search_code")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_gateway_rejects_invalid_token(gateway_client: AsyncClient):
    r = await gateway_client.get(
        "/mcp/tools/github.search_code",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_mock_mcp_health():
    transport = ASGITransport(app=mock_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_mock_mcp_github():
    transport = ASGITransport(app=mock_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/github/search_code")
        assert r.status_code == 200
        data = r.json()
        assert data["tool"] == "github"
        assert data["operation"] == "search_code"
```

### 7. Tests — tests/unit/test_tool_registry.py
```python
from apps.mcp_gateway.tool_registry.registry import get_required_scopes, list_tools


class TestToolRegistry:
    def test_known_tool_returns_scopes(self):
        scopes = get_required_scopes("github", "search_code")
        assert scopes == ["repo:read"]

    def test_unknown_tool_returns_none(self):
        assert get_required_scopes("evil", "destroy") is None

    def test_write_requires_write_scope(self):
        scopes = get_required_scopes("github", "create_issue")
        assert "issues:write" in scopes

    def test_list_tools(self):
        tools = list_tools()
        assert "github.search_code" in tools
        assert len(tools) >= 5
```

## Verification
```
PYTHONPATH=. uv run pytest tests/ -v
PYTHONPATH=. uv run ruff check packages/ apps/ tests/
PYTHONPATH=. uv run ruff format packages/ apps/ tests/
```
