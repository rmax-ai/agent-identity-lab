"""Policy evaluation service with scope intersection."""

from packages.policy_client.adapter import PolicyAdapter
from packages.policy_client.models import PolicyInput, PolicyOutput


class PolicyService:
    """Orchestrates policy evaluation for agent tool access."""

    def __init__(self, adapter: PolicyAdapter):
        self.adapter = adapter

    async def authorize_tool_access(
        self,
        agent: dict,
        blueprint: dict,
        user: dict,
        session: dict,
        runtime: dict,
        tool_id: str,
        operation: str,
        requested_scopes: list[str],
        environment: str = "development",
    ) -> PolicyOutput:
        """Evaluate whether an agent may access a tool with the given scopes."""
        policy_input = PolicyInput(
            agent=agent,
            blueprint=blueprint,
            user=user,
            session=session,
            runtime=runtime,
            tool={"id": tool_id},
            action={
                "operation": operation,
                "requested_scopes": requested_scopes,
            },
            environment={"name": environment},
        )
        return await self.adapter.evaluate(policy_input)
