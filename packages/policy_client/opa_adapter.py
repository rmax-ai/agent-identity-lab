"""OPA policy adapter using the OPA REST API."""

import httpx

from packages.common.settings import Settings
from packages.policy_client.adapter import PolicyAdapter
from packages.policy_client.models import PolicyInput, PolicyOutput


class OPAAdapter(PolicyAdapter):
    """Policy adapter that delegates to Open Policy Agent."""

    def __init__(self, settings: Settings):
        self.base_url = settings.opa_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=10.0)

    async def evaluate(self, policy_input: PolicyInput) -> PolicyOutput:
        try:
            response = await self.client.post(
                f"{self.base_url}/v1/data/agent_identity/tool_access",
                json={"input": policy_input.model_dump()},
            )
            response.raise_for_status()
            result = response.json().get("result", {})
        except httpx.HTTPError as exc:
            return PolicyOutput(
                decision="deny",
                reason=f"Policy service unavailable: {exc}",
                policy_version="opa-unavailable",
            )

        if result.get("allow"):
            return PolicyOutput(
                decision="allow",
                reason=result.get("reason", "Policy allowed"),
                effective_scopes=result.get("effective_scopes", []),
                obligations=result.get("obligations", []),
                policy_version=result.get("policy_version", "opa-0.0.0"),
            )

        return PolicyOutput(
            decision="deny",
            reason=result.get("deny_reason", result.get("reason", "Policy denied")),
            effective_scopes=result.get("effective_scopes", []),
            obligations=result.get("obligations", []),
            policy_version=result.get("policy_version", "opa-0.0.0"),
        )

    async def health(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        await self.client.aclose()
