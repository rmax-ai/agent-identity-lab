## Demo Walkthrough

Phase 7 ships six demo scenarios under `examples/` and corresponding `make` targets for the main cases. The scenarios cover: delegated authorized read, denied write attempt, suspended agent lifecycle enforcement, invalid runtime environment denial, downstream secret isolation, and machine-only execution without an acting user. Together they exercise the core identity, session, policy, and credential-leasing paths described in the spec.

Run the stack first with `docker compose up -d`, then execute demos from the repo root. `make demo-authorized-read` is the primary smoke test for the end-to-end flow. Additional targets include `make demo-denied-write`, `make demo-suspended-agent`, `make demo-invalid-runtime`, `make demo-secret-isolation`, and `make demo-machine-only`.

Each demo is designed to assert its own expected outcome and print a short PASS line when the behavior matches the platform contract. They are intentionally lightweight: the goal is not load testing, but showing an engineer or reviewer how the identity plane behaves when an agent asks for something it should or should not be allowed to do.
