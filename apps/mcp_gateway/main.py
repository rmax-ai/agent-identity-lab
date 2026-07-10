"""MCP Gateway — enforcement boundary between agents and MCP servers."""

import logging
import logging.config

from fastapi import FastAPI, HTTPException, Request

from apps.mcp_gateway.middleware.auth import GatewayAuth
from apps.mcp_gateway.proxy.forwarder import MCPForwarder
from packages.common.settings import Settings, settings

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {"handlers": ["console"], "level": settings.log_level},
        "loggers": {"mcp_gateway": {"level": settings.log_level, "propagate": False}},
    }
)
logger = logging.getLogger("mcp_gateway")


def create_app(app_settings: Settings | None = None) -> FastAPI:
    """Build the MCP Gateway app."""
    resolved_settings = app_settings or settings

    gateway_app = FastAPI(
        title="Agent Identity Lab — MCP Gateway",
        version="0.1.0",
    )
    gateway_app.state.auth = GatewayAuth(resolved_settings)
    gateway_app.state.forwarder = MCPForwarder()

    @gateway_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "mcp_gateway"}

    @gateway_app.api_route(
        "/mcp/tools/{tool_id}.{operation:path}",
        methods=["GET", "POST", "PUT", "DELETE"],
    )
    async def proxy_mcp_request(tool_id: str, operation: str, request: Request):
        auth: GatewayAuth = request.app.state.auth
        forwarder: MCPForwarder = request.app.state.forwarder

        claims = await auth.authenticate(request)

        try:
            auth_result = await auth.authorize(claims, tool_id, operation)
        except HTTPException:
            raise

        if auth_result.get("decision") != "allow":
            raise HTTPException(
                status_code=403,
                detail=auth_result.get("reason", "Access denied"),
            )

        return await forwarder.forward(
            request,
            tool_id=tool_id,
            operation=operation,
            downstream_credentials=auth_result.get("downstream_credentials"),
        )

    return gateway_app


app = create_app()
