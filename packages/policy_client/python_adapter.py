"""Python-native policy adapter."""

from typing import ClassVar

from packages.policy_client.adapter import PolicyAdapter
from packages.policy_client.models import PolicyInput, PolicyOutput


class PythonPolicyAdapter(PolicyAdapter):
    """Simple Python policy evaluator with scope intersection."""

    TOOL_SCOPE_MAP: ClassVar[dict[str, dict[str, list[str]]]] = {
        "github.search_code": {"required_scopes": ["repo:read"]},
        "github.create_issue": {"required_scopes": ["issues:write"]},
        "github.list_repos": {"required_scopes": ["repo:read"]},
        "github.list_issues": {"required_scopes": ["issues:read"]},
        "confluence.search": {"required_scopes": ["pages:read"]},
        "confluence.create_page": {"required_scopes": ["pages:write"]},
    }

    async def evaluate(self, policy_input: PolicyInput) -> PolicyOutput:
        agent = policy_input.agent
        blueprint = policy_input.blueprint
        user = policy_input.user
        tool = policy_input.tool
        action = policy_input.action
        runtime = policy_input.runtime

        if agent.get("status") != "active":
            return PolicyOutput(
                decision="deny",
                reason="Agent is not active",
                policy_version="python-1.0",
            )

        if blueprint.get("status") != "active":
            return PolicyOutput(
                decision="deny",
                reason="Blueprint is not active",
                policy_version="python-1.0",
            )

        tool_id = tool.get("id", "")
        operation = action.get("operation", "")
        tool_key = f"{tool_id}.{operation}" if tool_id and operation else tool_id
        required = self.TOOL_SCOPE_MAP.get(tool_key)
        if required is None:
            return PolicyOutput(
                decision="deny",
                reason=f"Unknown tool or operation: {tool_key}",
                policy_version="python-1.0",
            )

        if blueprint.get("slug") == "research-agent" and any(
            scope.endswith(":write") for scope in required["required_scopes"]
        ):
            return PolicyOutput(
                decision="deny",
                reason="Research agents cannot perform write operations",
                policy_version="python-1.0",
            )

        approved_envs = blueprint.get("approved_environments", [])
        env = runtime.get("environment", "")
        if approved_envs and env not in approved_envs:
            return PolicyOutput(
                decision="deny",
                reason=f"Environment '{env}' not in approved environments",
                policy_version="python-1.0",
            )

        agent_scopes = set(agent.get("scopes", []))
        blueprint_scopes = set(blueprint.get("max_scopes", []))
        user_scopes = set(user.get("scopes", []))
        tool_required = set(required["required_scopes"])
        requested = set(action.get("requested_scopes", required["required_scopes"]))

        effective = requested & agent_scopes & blueprint_scopes & tool_required
        if user_scopes:
            effective &= user_scopes

        if not effective:
            removed = sorted(requested - effective)
            return PolicyOutput(
                decision="deny",
                reason=f"No scopes remain after intersection. Removed: {removed}",
                effective_scopes=[],
                policy_version="python-1.0",
            )

        return PolicyOutput(
            decision="allow",
            reason="Permission intersection satisfied",
            effective_scopes=sorted(effective),
            obligations=["log_request"],
            policy_version="python-1.0",
        )

    async def health(self) -> bool:
        return True
