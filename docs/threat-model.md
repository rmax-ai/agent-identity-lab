## Threat Model

The system assumes an AI agent runtime is powerful enough to misuse credentials, escalate scopes, or act outside the operator's intent if not constrained. The threat model therefore treats the runtime as partially trusted: it may hold a valid session token, but it must still prove where it is running, which agent identity it represents, and what scopes it is requesting. Replay, forged attestations, stale sessions, and unauthorized write attempts are all first-class concerns.

The main defensive controls are layered. Runtime attestations are signed and freshness-checked. Session tokens are short-lived and revocable. Authorization decisions intersect blueprint, agent, requested, tool, and optionally user scopes. Token exchange is separated from identity issuance so downstream credentials can be rotated and logged without exposing source secrets to the agent itself.

The MVP does not claim full hardware-backed attestation or complete insider-risk protection. It is designed to make abuse visible, narrow blast radius, and ensure a single agent action can be reconstructed after the fact with enough context to support incident response and policy tuning.
