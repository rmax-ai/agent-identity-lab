"""Forward authorized requests to downstream MCP servers."""

from urllib.parse import urlencode

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response


class MCPForwarder:
    """Forward requests from the gateway to a downstream MCP server."""

    def __init__(
        self,
        mcp_server_url: str = "http://localhost:8003",
        client: httpx.AsyncClient | None = None,
    ):
        self.mcp_url = mcp_server_url.rstrip("/")
        self.client = client

    async def forward(
        self,
        request: Request,
        tool_id: str,
        operation: str,
        downstream_credentials: dict | None = None,
    ) -> Response:
        """Forward the request to the MCP server, injecting credentials if present."""
        body = await request.body()
        headers = dict(request.headers)

        headers.pop("host", None)
        headers.pop("authorization", None)

        if downstream_credentials:
            cred_type = downstream_credentials.get("type", "bearer")
            if cred_type == "bearer":
                headers["authorization"] = f"Bearer {downstream_credentials.get('token', '')}"
            elif cred_type == "header":
                header_name = downstream_credentials.get("header_name", "X-Api-Key")
                headers[header_name] = downstream_credentials.get("token", "")

        trace_id = request.headers.get("X-Agent-Trace-ID", "")
        if trace_id:
            headers["X-Trace-ID"] = trace_id

        target_url = f"{self.mcp_url}/{tool_id}/{operation}"
        query_params = dict(request.query_params)
        if query_params:
            target_url = f"{target_url}?{urlencode(query_params, doseq=True)}"

        try:
            client = self.client or httpx.AsyncClient(timeout=30.0)
            self.client = client
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
        except httpx.HTTPError as exc:
            return JSONResponse(content={"error": str(exc)}, status_code=502)

        content_type = response.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            return JSONResponse(content=response.json(), status_code=response.status_code)

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=content_type or None,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self.client is not None:
            await self.client.aclose()
