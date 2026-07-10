## Token Model

Agent Identity Lab issues short-lived JWT session credentials that represent an approved agent execution context. A token binds together the agent identity, optional acting user, trace identifier, effective scopes, model metadata, issuance time, and expiration time. The token is signed asymmetrically so verifiers can validate it without sharing a symmetric secret across services.

The JWT is intentionally not the same as a downstream tool credential. It proves that the identity plane approved a particular session; it does not grant direct GitHub, Confluence, or MCP access on its own. Services such as `mcp_gateway` and `token_broker` consume the JWT, validate it, and then decide whether to authorize a tool request or mint a narrower downstream lease.

This separation is what keeps the token model defensible. Session tokens are portable inside the platform and easy to audit, while tool credentials remain short-lived, scoped, and replaceable. If a session is revoked or expires, every later authorization or exchange attempt should fail even if an agent still holds the old JWT string.
