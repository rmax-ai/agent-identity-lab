"""Unit tests for runtime attestation verification."""

import uuid
from datetime import UTC, datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from packages.attestation.verifier import AttestationVerifier
from packages.common.enums import VerificationResult


def make_keypair():
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
    return private_pem.decode(), public_pem.decode()


def make_attestation(agent_id, **overrides):
    data = {
        "agent_id": agent_id,
        "container_digest": "sha256:abc123",
        "git_commit": "abc123def456",
        "environment": "development",
        "host_id": "docker-local-01",
        "framework": "hermes",
        "framework_version": "0.4.0",
        "model": "deepseek-chat",
        "prompt_version": "research-v3",
        "issued_at": datetime.now(UTC).isoformat(),
        "nonce": str(uuid.uuid4()),
    }
    data.update(overrides)
    return data


class TestAttestationVerifier:
    def test_valid_attestation(self):
        agent_id = str(uuid.uuid4())
        private_pem, public_pem = make_keypair()
        claims = make_attestation(agent_id)
        sig = AttestationVerifier.sign_attestation(claims, private_pem)

        result, reason = AttestationVerifier.verify(claims, sig, public_pem, agent_id)
        assert result == VerificationResult.VERIFIED
        assert reason == "All checks passed"

    def test_agent_id_mismatch(self):
        agent_id = str(uuid.uuid4())
        private_pem, public_pem = make_keypair()
        claims = make_attestation(agent_id)
        sig = AttestationVerifier.sign_attestation(claims, private_pem)

        result, reason = AttestationVerifier.verify(
            claims,
            sig,
            public_pem,
            str(uuid.uuid4()),
        )
        assert result == VerificationResult.REJECTED
        assert "Agent ID mismatch" in reason

    def test_replay_attack_blocked(self):
        agent_id = str(uuid.uuid4())
        private_pem, public_pem = make_keypair()
        claims = make_attestation(agent_id, nonce="replay-nonce-123")
        sig = AttestationVerifier.sign_attestation(claims, private_pem)

        result1, _ = AttestationVerifier.verify(claims, sig, public_pem, agent_id)
        assert result1 == VerificationResult.VERIFIED

        result2, reason2 = AttestationVerifier.verify(claims, sig, public_pem, agent_id)
        assert result2 == VerificationResult.REJECTED
        assert "already seen" in reason2

    def test_missing_required_claim(self):
        agent_id = str(uuid.uuid4())
        private_pem, public_pem = make_keypair()
        claims = make_attestation(agent_id)
        del claims["container_digest"]
        sig = AttestationVerifier.sign_attestation(claims, private_pem)

        result, reason = AttestationVerifier.verify(claims, sig, public_pem, agent_id)
        assert result == VerificationResult.REJECTED
        assert "missing" in reason.lower()

    def test_invalid_signature(self):
        agent_id = str(uuid.uuid4())
        private_pem, public_pem = make_keypair()
        claims = make_attestation(agent_id)
        sig = AttestationVerifier.sign_attestation(claims, private_pem)
        claims["container_digest"] = "sha256:evil"

        result, reason = AttestationVerifier.verify(claims, sig, public_pem, agent_id)
        assert result == VerificationResult.REJECTED
        assert "Signature" in reason
