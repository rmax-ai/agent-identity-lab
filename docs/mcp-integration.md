## MCP Integration

`mcp_gateway` is the integration point between agent runtimes and MCP servers. Its job is not just routing. It validates the session token, asks `identity_api` for an authorization decision on the requested tool operation, and only forwards the call when the request is still within the approved session context. This makes the gateway the concrete enforcement boundary in front of tool execution.

In a production flow, the gateway should combine session validation, policy decision, credential injection, and audit logging into one path. The agent should send its intent and session token; the gateway should resolve any required downstream credential server-side and then call the target MCP server without exposing that credential back to the runtime. The included `mock_mcp_server` gives the repo a local target for testing that behavior end to end.

The practical integration rule is simple: agents should never bypass the gateway when using external tools. Once tool access goes around the gateway, the platform loses centralized policy enforcement, consistent audit trails, and the ability to guarantee that downstream credentials remain isolated from the agent process.
