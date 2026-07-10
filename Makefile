.PHONY: run test lint format check demo-authorized-read demo-denied-write demo-suspended-agent demo-invalid-runtime demo-secret-isolation demo-machine-only

run:
	docker compose up -d

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check apps/ packages/ tests/

format:
	uv run ruff format apps/ packages/ tests/

check: lint format
	uv run ty check

# Demo scenarios (post-MVP)
demo-authorized-read:
	@echo "Running authorized read demo..."
	uv run python examples/delegated_research/authorized_read.py

demo-denied-write:
	@echo "Running denied write demo..."
	uv run python examples/unauthorized_write_attempt/denied_write.py

demo-suspended-agent:
	@echo "Running suspended agent demo..."
	uv run python examples/hermes_agent/suspended_agent.py

demo-invalid-runtime:
	@echo "Running invalid runtime demo..."
	uv run python examples/hermes_agent/invalid_runtime.py

demo-secret-isolation:
	@echo "Running secret isolation demo..."
	uv run python examples/delegated_research/secret_isolation.py

demo-machine-only:
	@echo "Running machine-only session demo..."
	uv run python examples/hermes_agent/machine_only_session.py
