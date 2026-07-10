## Policy Model

The policy model evaluates access from multiple dimensions instead of relying on a single role or service account. In the MVP, the effective permission set is the intersection of what the session requested, what the agent currently holds, what the blueprint allows, what the tool operation requires, and, when available, what the acting user is allowed to do. If nothing survives that intersection, the request is denied.

Policy inputs include agent lifecycle state, blueprint status, runtime environment, tool identifier, operation, and requested scopes. That means a request can fail even with a valid session token if the runtime is unapproved, the agent has been suspended, or the tool operation requires a scope that is outside the blueprint contract. This is the key difference between identity-based authorization and simple bearer-token forwarding.

The repo supports both a Python adapter and an OPA-backed adapter behind the same service boundary. That lets the implementation start simple while keeping the decision interface stable for future production policy bundles, richer attributes, and environment-specific policy packs.
