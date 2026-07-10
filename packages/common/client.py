"""Agent Identity Client SDK — integration library for AI agent runtimes."""

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from packages.attestation.verifier import AttestationVerifier


class AgentIdentityClient:
    """Client for Hermes and other agent runtimes to integrate with Agent Identity Lab."""

    def __init__(self, identity_api_url: str = "http://localhost:8000"):
        self.api_url = identity_api_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self._private_key: str | None = None

    def generate_keypair(self) -> tuple[str, str]:
        """Generate an RSA keypair and retain the private key for attestation signing."""
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        public_pem = (
            key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        self._private_key = private_pem
        return private_pem, public_pem

    async def create_session(
        self,
        agent_id: str,
        acting_user_id: str | None,
        requested_scopes: list[str],
        model_id: str = "deepseek-chat",
        prompt_version: str = "v1",
        *,
        environment: str = "development",
        attestation_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a session with a signed runtime attestation."""
        if self._private_key is None:
            raise ValueError("No private key available. Call generate_keypair() first.")

        claims: dict[str, Any] = {
            "agent_id": agent_id,
            "container_digest": "sha256:dev",
            "git_commit": "dev",
            "environment": environment,
            "host_id": "localhost",
            "framework": "hermes",
            "framework_version": "0.4.0",
            "model": model_id,
            "prompt_version": prompt_version,
            "issued_at": datetime.now(UTC).isoformat(),
            "nonce": str(uuid.uuid4()),
        }
        if attestation_overrides:
            claims.update(attestation_overrides)

        signature = AttestationVerifier.sign_attestation(claims, self._private_key)
        response = await self.client.post(
            f"{self.api_url}/v1/sessions",
            json={
                "agent_id": agent_id,
                "acting_user_id": acting_user_id,
                "requested_scopes": requested_scopes,
                "requested_ttl_seconds": 900,
                "model_id": model_id,
                "prompt_version": prompt_version,
                "runtime_attestation": {**claims, "signature": signature},
            },
        )
        response.raise_for_status()
        return response.json()

    async def authorize(self, session_token: str, tool: str, operation: str) -> dict[str, Any]:
        """Request a tool authorization decision for an existing session token."""
        response = await self.client.post(
            f"{self.api_url}/v1/authorize",
            json={
                "session_token": session_token,
                "tool": tool,
                "operation": operation,
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
