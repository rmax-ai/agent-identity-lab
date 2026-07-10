"""JWT token validation for Agent Session Tokens."""

from typing import Any

import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidSignatureError,
    InvalidTokenError,
)

from packages.common.settings import Settings
from packages.token_library.keys import load_public_key


def validate_session_token(token: str, settings: Settings) -> dict[str, Any]:
    """Validate and decode an Agent Session Token."""
    public_key = load_public_key(settings)
    options = {"require": ["exp", "iat", "jti", "iss", "aud", "sub"]}

    try:
        claims = jwt.decode(
            token,
            public_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options=options,
        )
    except ExpiredSignatureError as exc:
        raise ValueError("Token has expired") from exc
    except InvalidAudienceError as exc:
        raise ValueError("Invalid token audience") from exc
    except InvalidSignatureError as exc:
        raise ValueError("Invalid token signature") from exc
    except InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc

    required_claims = ["agent_id", "scopes", "trace_id"]
    missing = [claim for claim in required_claims if claim not in claims]
    if missing:
        raise ValueError(f"Missing required claims: {missing}")
    if not isinstance(claims.get("scopes"), list):
        raise ValueError("scopes claim must be a list")

    return claims
