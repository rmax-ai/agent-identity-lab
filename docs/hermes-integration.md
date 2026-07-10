## Hermes Integration

Hermes integrates with Agent Identity Lab through the `AgentIdentityClient` in [`packages/common/client.py`](/home/rmax-10/src/agent-identity-lab/packages/common/client.py). The runtime generates an RSA keypair, registers the public key with the agent identity, and uses the private key to sign a runtime attestation each time it creates a session. That attestation carries the agent identifier, environment, framework version, model, prompt version, issuance time, and nonce.

Once Hermes receives a session token, it should treat that token as proof of platform-approved identity, not as a general-purpose secret. For each tool call, Hermes asks `/v1/authorize` for the specific tool and operation it wants to execute. If authorized, the rest of the tool path should go through `mcp_gateway` or `token_broker` so downstream credentials remain leased and auditable rather than embedded in the runtime.

The demo scenarios in `examples/` show the expected outcomes for normal and failure cases: authorized read, denied write, invalid runtime environment, suspended agent behavior, secret isolation, and machine-only execution. That gives Hermes or any similar runtime a concrete reference implementation for the control-plane handshake.
