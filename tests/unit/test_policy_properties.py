"""Property-based tests for policy invariants using Hypothesis."""

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from packages.policy_client.models import PolicyInput
from packages.policy_client.python_adapter import PythonPolicyAdapter

statuses = st.sampled_from(["active", "suspended", "revoked", "draft"])
scopes_list = st.lists(
    st.sampled_from(
        [
            "repo:read",
            "repo:write",
            "issues:read",
            "issues:write",
            "pages:read",
            "pages:write",
        ]
    ),
    min_size=0,
    max_size=4,
    unique=True,
)


@given(statuses, scopes_list, scopes_list)
@pytest.mark.asyncio
async def test_effective_scopes_are_subset_of_requested(
    agent_status,
    agent_scopes,
    requested_scopes,
):
    assume(len(requested_scopes) > 0)
    result = await PythonPolicyAdapter().evaluate(
        PolicyInput(
            agent={"status": agent_status, "scopes": agent_scopes},
            blueprint={
                "status": "active",
                "max_scopes": agent_scopes,
                "slug": "custom-agent",
            },
            tool={"id": "github"},
            action={"operation": "search_code", "requested_scopes": requested_scopes},
        )
    )
    if result.decision == "allow":
        assert set(result.effective_scopes) <= set(requested_scopes)


@given(statuses, scopes_list)
@pytest.mark.asyncio
async def test_revoked_agent_always_denied(agent_status, scopes):
    assume(agent_status != "active")
    result = await PythonPolicyAdapter().evaluate(
        PolicyInput(
            agent={"status": agent_status, "scopes": scopes},
            blueprint={"status": "active", "max_scopes": scopes},
            tool={"id": "github"},
            action={"operation": "search_code", "requested_scopes": scopes},
        )
    )
    assert result.decision == "deny"
