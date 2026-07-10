"""Unit tests for the MCP tool registry."""

from apps.mcp_gateway.tool_registry.registry import get_required_scopes, list_tools


class TestToolRegistry:
    def test_known_tool_returns_scopes(self):
        scopes = get_required_scopes("github", "search_code")
        assert scopes == ["repo:read"]

    def test_unknown_tool_returns_none(self):
        assert get_required_scopes("evil", "destroy") is None

    def test_write_requires_write_scope(self):
        scopes = get_required_scopes("github", "create_issue")
        assert scopes is not None
        assert "issues:write" in scopes

    def test_list_tools(self):
        tools = list_tools()
        assert "github.search_code" in tools
        assert len(tools) >= 5
