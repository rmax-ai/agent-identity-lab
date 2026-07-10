"""Unit tests for scope intersection logic."""

import pytest

from packages.policy_client.models import PolicyInput
from packages.policy_client.python_adapter import PythonPolicyAdapter


@pytest.fixture
def adapter():
    return PythonPolicyAdapter()


@pytest.mark.asyncio
async def test_allow_read_for_active_agent(adapter):
    result = await adapter.evaluate(
        PolicyInput(
            agent={"status": "active", "scopes": ["repo:read"]},
            blueprint={
                "status": "active",
                "max_scopes": ["repo:read"],
                "approved_environments": ["development"],
            },
            user={"scopes": ["repo:read"]},
            tool={"id": "github"},
            action={"operation": "search_code", "requested_scopes": ["repo:read"]},
            runtime={"environment": "development"},
        )
    )
    assert result.decision == "allow"
    assert "repo:read" in result.effective_scopes


@pytest.mark.asyncio
async def test_deny_inactive_agent(adapter):
    result = await adapter.evaluate(
        PolicyInput(
            agent={"status": "suspended", "scopes": ["repo:read"]},
            blueprint={"status": "active", "max_scopes": ["repo:read"]},
            tool={"id": "github"},
            action={"operation": "search_code", "requested_scopes": ["repo:read"]},
        )
    )
    assert result.decision == "deny"


@pytest.mark.asyncio
async def test_deny_research_agent_write(adapter):
    result = await adapter.evaluate(
        PolicyInput(
            agent={"status": "active", "scopes": ["issues:write"]},
            blueprint={
                "status": "active",
                "slug": "research-agent",
                "max_scopes": ["issues:write"],
            },
            tool={"id": "github"},
            action={"operation": "create_issue", "requested_scopes": ["issues:write"]},
        )
    )
    assert result.decision == "deny"
    assert "Research" in result.reason


@pytest.mark.asyncio
async def test_deny_unknown_tool(adapter):
    result = await adapter.evaluate(
        PolicyInput(
            agent={"status": "active", "scopes": ["admin:all"]},
            blueprint={"status": "active", "max_scopes": ["admin:all"]},
            tool={"id": "dangerous_tool"},
            action={"operation": "do_bad_thing", "requested_scopes": ["admin:all"]},
        )
    )
    assert result.decision == "deny"
    assert "Unknown tool" in result.reason


@pytest.mark.asyncio
async def test_scope_intersection_reduces(adapter):
    """Requested 3 scopes, agent only has 2, blueprint has 1."""
    result = await adapter.evaluate(
        PolicyInput(
            agent={"status": "active", "scopes": ["repo:read", "issues:read"]},
            blueprint={
                "status": "active",
                "max_scopes": ["repo:read"],
                "approved_environments": [],
            },
            tool={"id": "github"},
            action={
                "operation": "search_code",
                "requested_scopes": ["repo:read", "issues:read", "issues:write"],
            },
        )
    )
    assert result.decision == "allow"
    assert result.effective_scopes == ["repo:read"]


@pytest.mark.asyncio
async def test_deny_wrong_environment(adapter):
    result = await adapter.evaluate(
        PolicyInput(
            agent={"status": "active", "scopes": ["repo:read"]},
            blueprint={
                "status": "active",
                "max_scopes": ["repo:read"],
                "approved_environments": ["staging"],
            },
            tool={"id": "github"},
            action={"operation": "search_code", "requested_scopes": ["repo:read"]},
            runtime={"environment": "production"},
        )
    )
    assert result.decision == "deny"
    assert "Environment" in result.reason
