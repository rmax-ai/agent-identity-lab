"""JWT token issuance for Agent Session Tokens."""

from datetime import UTC, datetime

import jwt

from packages.common.settings import Settings
from packages.identity_models.session import AgentSession
from packages.token_library.keys import load_private_key


def issue_session_token(
    session: AgentSession,
    settings: Settings,
    blueprint_id: str = "unknown",
) -> str:
    """Issue a signed JWT for an agent session."""
    private_key = load_private_key(settings)
    now = datetime.now(UTC)

    claims = {
        "iss": settings.jwt_issuer,
        "sub": f"agent:{session.agent_id}",
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(session.expires_at.timestamp()),
        "jti": str(session.id),
        "agent_id": str(session.agent_id),
        "blueprint_id": blueprint_id,
        "acting_user": session.acting_user_id,
        "delegation_id": str(session.delegation_grant_id) if session.delegation_grant_id else None,
        "scopes": session.effective_scopes,
        "model": session.model_id,
        "prompt_version": session.prompt_version,
        "trace_id": session.trace_id,
        "policy_version": session.policy_version,
    }

    return jwt.encode(claims, private_key, algorithm=settings.jwt_algorithm)
