## Architecture

Agent Identity Lab is split into shared logic in `packages/` and deployable services in `apps/`. `identity_api` owns blueprints, agents, sessions, delegation state, and policy orchestration. `token_broker` turns an approved session into a downstream credential lease. `mcp_gateway` is the enforcement edge between agents and MCP tools, while `mock_mcp_server` exists to exercise the flow locally. The `admin_ui` is the operator-facing surface for inspection and lifecycle control.

The main trust path is: agent runtime presents a signed attestation to `identity_api`, the service validates the agent and blueprint lifecycle state, issues a short-lived JWT session token, and records enough metadata to trace the decision later. When the runtime asks to use a tool, `mcp_gateway` or the client calls `/v1/authorize`, which evaluates policy from agent, blueprint, runtime, session, and requested operation context before allowing access.

This structure keeps identities, policy, credential issuance, and tool execution decoupled. The system can evolve each layer independently, but the enforcement boundary remains explicit: agents do not talk to downstream tools with raw secrets, and operators can inspect each action through sessions, authorization decisions, and audit records.
