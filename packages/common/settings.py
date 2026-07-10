"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Agent Identity Lab configuration."""

    # Database
    database_url: str = "postgresql+asyncpg://ail:ail_dev@localhost:5432/agent_identity_lab"

    # OPA
    opa_url: str = "http://localhost:8181"

    # JWT signing keys
    jwt_private_key_path: str = "./keys/private.pem"
    jwt_public_key_path: str = "./keys/public.pem"
    jwt_algorithm: str = "RS256"
    jwt_audience: str = "mcp-gateway"
    jwt_issuer: str = "agent-identity-lab"
    jwt_max_ttl_seconds: int = 1800  # 30 minutes

    # Admin auth
    admin_api_key: str = "dev-admin-key-change-in-production"

    # Service URLs
    identity_api_url: str = "http://localhost:8000"
    token_broker_url: str = "http://localhost:8001"
    mcp_gateway_url: str = "http://localhost:8002"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Logging
    log_level: str = "DEBUG"

    # Session
    session_max_ttl_seconds: int = 1800

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
