# Phase 7: Hermes Integration + Demos + Documentation

Implement the Python client SDK, 6 demo scenarios, and all documentation deliverables.

**Context:** Phases 1-6 complete. Working: blueprints, agents, sessions, policy, gateway, token broker, audit chain. Admin UI scaffold exists.

**Test:** `PYTHONPATH=. uv run pytest tests/ -v`

## Files to Create

### 1. packages/common/client.py — AgentIdentityClient SDK
```python
"""Agent Identity Client SDK — integration library for AI agent runtimes."""

import uuid
from datetime import datetime, timezone
import httpx
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from packages.attestation.verifier import AttestationVerifier

class AgentIdentityClient:
    """Client for Hermes and other agent runtimes to integrate with Agent Identity Lab."""

    def __init__(self, identity_api_url: str = "http://localhost:8000"):
        self.api_url = identity_api_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self._private_key: str | None = None

    def generate_keypair(self) -> tuple[str, str]:
        """Generate RSA keypair for agent identity. Returns (private_pem, public_pem)."""
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        public_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        self._private_key = private_pem
        return private_pem, public_pem

    async def create_session(
        self,
        agent_id: str,
        acting_user_id: str | None,
        requested_scopes: list[str],
        model_id: str = "deepseek-chat",
        prompt_version: str = "v1",
    ) -> dict:
        """Create an agent session with signed runtime attestation."""
        claims = {
            "agent_id": agent_id,
            "container_digest": "sha256:dev",
            "git_commit": "dev",
            "environment": "development",
            "host_id": "localhost",
            "framework": "hermes",
            "framework_version": "0.4.0",
            "model": model_id,
            "prompt_version": prompt_version,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "nonce": str(uuid.uuid4()),
        }
        sig = AttestationVerifier.sign_attestation(claims, self._private_key or "")

        r = await self.client.post(f"{self.api_url}/v1/sessions", json={
            "agent_id": agent_id,
            "acting_user_id": acting_user_id,
            "requested_scopes": requested_scopes,
            "requested_ttl_seconds": 900,
            "model_id": model_id,
            "prompt_version": prompt_version,
            "runtime_attestation": {**claims, "signature": sig},
        })
        r.raise_for_status()
        return r.json()

    async def authorize(self, session_token: str, tool: str, operation: str) -> dict:
        r = await self.client.post(f"{self.api_url}/v1/authorize", json={
            "session_token": session_token, "tool": tool, "operation": operation,
        })
        r.raise_for_status()
        return r.json()

    async def close(self):
        await self.client.aclose()
```

### 2. examples/delegated_research/authorized_read.py
```python
"""Demo: Authorized read access — Research Agent reads a GitHub repository."""
import asyncio
import uuid
import httpx

async def demo():
    api = "http://localhost:8000"
    admin_headers = {"X-Admin-API-Key": "test-admin-key"}
    async with httpx.AsyncClient() as c:
        # 1. Create blueprint
        bp = await c.post(f"{api}/v1/blueprints", json={"slug": "demo-research", "name": "Demo Research Agent", "max_scopes": ["repo:read", "issues:read"]}, headers=admin_headers)
        bp_id = bp.json()["id"]
        await c.post(f"{api}/v1/blueprints/{bp_id}/activate", headers=admin_headers)
        # 2. Create agent with key
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        key = rsa.generate_private_key(65537, 2048)
        pub = key.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        priv = key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()).decode()
        agent = await c.post(f"{api}/v1/agents", json={"blueprint_id": bp_id, "owner_id": "demo_user", "public_key": pub}, headers=admin_headers)
        agent_id = agent.json()["id"]
        await c.post(f"{api}/v1/agents/{agent_id}/activate", headers=admin_headers)
        # 3. Create session
        from packages.attestation.verifier import AttestationVerifier
        from datetime import datetime, timezone
        claims = {"agent_id": agent_id, "container_digest": "sha256:demo", "git_commit": "demo", "environment": "development", "host_id": "localhost", "framework": "hermes", "framework_version": "0.4.0", "model": "deepseek-chat", "prompt_version": "v1", "issued_at": datetime.now(timezone.utc).isoformat(), "nonce": str(uuid.uuid4())}
        sig = AttestationVerifier.sign_attestation(claims, priv)
        sess = await c.post(f"{api}/v1/sessions", json={"agent_id": agent_id, "acting_user_id": "demo_user", "requested_scopes": ["repo:read"], "model_id": "deepseek-chat", "runtime_attestation": {**claims, "signature": sig}})
        token = sess.json()["token"]
        # 4. Authorize
        auth = await c.post(f"{api}/v1/authorize", json={"session_token": token, "tool": "github", "operation": "search_code"})
        result = auth.json()
        print(f"Demo: Authorized Read — decision={result['decision']}, scopes={result['effective_scopes']}")
        assert result["decision"] == "allow", "Expected allow!"
        print("✅ PASS")

if __name__ == "__main__":
    asyncio.run(demo())
```

### 3. examples/unauthorized_write_attempt/denied_write.py
Similar to above but request issues:write scope against a research agent. Expect deny.

### 4. examples/hermes_agent/suspended_agent.py
Create agent, activate, create session, then suspend agent, try another session — expect 400.

### 5. examples/hermes_agent/invalid_runtime.py
Create session with wrong environment in attestation — expect deny.

### 6. examples/delegated_research/secret_isolation.py
Create session, request downstream credential via token broker — verify no raw secret in response.

### 7. docs/architecture.md, docs/threat-model.md, docs/token-model.md, docs/policy-model.md, docs/mcp-integration.md, docs/hermes-integration.md, docs/demo.md
Summary docs (2-3 paragraphs each) describing the system. Read SPEC.md for source material.

### 8. docs/adr/ADR-001 through ADR-007
One file per ADR (2-3 paragraphs each). Read SPEC.md section 23 for ADR topics.

## Verification
All tests pass + lint/format clean + `make demo-authorized-read` runs successfully.
