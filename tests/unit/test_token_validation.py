"""Unit tests for JWT token issuance and validation."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from packages.common.settings import Settings
from packages.identity_models.session import AgentSession
from packages.token_library.issuer import issue_session_token
from packages.token_library.validator import validate_session_token


@pytest.fixture
def test_settings(tmp_path):
    """Generate test RSA keys and return settings pointing to them."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_path = tmp_path / "private.pem"
    public_path = tmp_path / "public.pem"
    private_path.write_bytes(private_pem)
    public_path.write_bytes(public_pem)

    return Settings(
        jwt_private_key_path=str(private_path),
        jwt_public_key_path=str(public_path),
        jwt_algorithm="RS256",
        jwt_issuer="agent-identity-lab",
        jwt_audience="mcp-gateway",
    )


def make_session(**overrides):
    now = datetime.now(UTC)
    defaults = {
        "id": uuid.uuid4(),
        "agent_id": uuid.uuid4(),
        "acting_user_id": "usr_test",
        "delegation_grant_id": None,
        "model_id": "deepseek-chat",
        "prompt_version": "v1",
        "runtime_attestation_id": uuid.uuid4(),
        "requested_scopes": ["repo:read"],
        "effective_scopes": ["repo:read"],
        "policy_version": "0.1.0",
        "trace_id": "trace_test123",
        "issued_at": now,
        "expires_at": now + timedelta(seconds=900),
        "revoked_at": None,
    }
    defaults.update(overrides)
    return AgentSession(**defaults)


class TestTokenIssuance:
    def test_issue_and_validate(self, test_settings):
        session = make_session()
        token = issue_session_token(session, test_settings, blueprint_id="bp-test:v1")

        claims = validate_session_token(token, test_settings)
        assert claims["agent_id"] == str(session.agent_id)
        assert claims["scopes"] == ["repo:read"]
        assert claims["blueprint_id"] == "bp-test:v1"

    def test_expired_token_rejected(self, test_settings):
        session = make_session(
            issued_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        token = issue_session_token(session, test_settings)

        with pytest.raises(ValueError, match="expired"):
            validate_session_token(token, test_settings)

    def test_wrong_audience_rejected(self, test_settings):
        session = make_session()
        token = issue_session_token(session, test_settings)

        wrong_settings = Settings(
            jwt_public_key_path=test_settings.jwt_public_key_path,
            jwt_algorithm="RS256",
            jwt_issuer="agent-identity-lab",
            jwt_audience="wrong-audience",
        )
        with pytest.raises(ValueError, match="audience"):
            validate_session_token(token, wrong_settings)

    def test_wrong_signature_rejected(self, test_settings):
        session = make_session()
        token = issue_session_token(session, test_settings)
        tampered = token[:-4] + "XXXX"

        with pytest.raises(ValueError, match="signature"):
            validate_session_token(tampered, test_settings)

    def test_machine_only_session_no_user(self, test_settings):
        session = make_session(acting_user_id=None)
        token = issue_session_token(session, test_settings)
        claims = validate_session_token(token, test_settings)
        assert claims["acting_user"] is None
