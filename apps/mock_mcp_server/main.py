"""Mock MCP Server for development and testing."""

from fastapi import FastAPI, Request

app = FastAPI(title="Mock MCP Server", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "mock_mcp_server"}


@app.api_route("/github/{operation:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def github_tools(operation: str, request: Request) -> dict[str, str]:
    body = await request.json() if request.method in {"POST", "PUT"} else {}
    return {
        "tool": "github",
        "operation": operation,
        "result": f"Mock: {operation} completed successfully",
        "trace_id": request.headers.get("X-Trace-ID", ""),
        "auth_header": request.headers.get("authorization", ""),
        "body": str(body),
    }


@app.api_route("/confluence/{operation:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def confluence_tools(operation: str, request: Request) -> dict[str, str]:
    return {
        "tool": "confluence",
        "operation": operation,
        "result": f"Mock: {operation} completed successfully",
        "trace_id": request.headers.get("X-Trace-ID", ""),
    }
