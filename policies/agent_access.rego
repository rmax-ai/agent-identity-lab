package agent_identity.tool_access

import rego.v1

default allow := false
default deny_reason := "Access denied by default - no matching allow rule"

allow if {
    input.agent.status == "active"
    input.blueprint.status == "active"
    input.tool.id == "github"
    input.action.operation == "search_code"
    "repo:read" in input.action.requested_scopes
}

allow if {
    input.agent.status == "active"
    input.blueprint.status == "active"
    input.tool.id == "github"
    input.action.operation == "list_issues"
    "issues:read" in input.action.requested_scopes
}

allow if {
    input.agent.status == "active"
    input.blueprint.status == "active"
    input.tool.id == "confluence"
    input.action.operation == "search"
    "pages:read" in input.action.requested_scopes
}

deny_reason := "Research agents cannot perform write operations" if {
    input.blueprint.slug == "research-agent"
    some scope in input.action.requested_scopes
    endswith(scope, ":write")
}

effective_scopes := [scope |
    some scope in input.action.requested_scopes
    scope in input.agent.scopes
    scope in input.blueprint.max_scopes
]
