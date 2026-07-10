"""Tool registry: maps MCP tool operations to required scopes."""

TOOL_MAPPINGS = {
    "github.search_code": {"required_scopes": ["repo:read"]},
    "github.list_repos": {"required_scopes": ["repo:read"]},
    "github.create_issue": {"required_scopes": ["issues:write"]},
    "github.list_issues": {"required_scopes": ["issues:read"]},
    "github.read_file": {"required_scopes": ["repo:read"]},
    "confluence.search": {"required_scopes": ["pages:read"]},
    "confluence.create_page": {"required_scopes": ["pages:write"]},
    "confluence.update_page": {"required_scopes": ["pages:write"]},
}


def get_required_scopes(tool_id: str, operation: str) -> list[str] | None:
    """Return the scopes required for a tool operation."""
    key = f"{tool_id}.{operation}"
    mapping = TOOL_MAPPINGS.get(key)
    if mapping:
        return mapping["required_scopes"]
    return None


def list_tools() -> list[str]:
    """List known tool operations."""
    return list(TOOL_MAPPINGS.keys())
