"""Runtime attestation verification."""

import json
from datetime import UTC, datetime
from typing import Any, ClassVar

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from packages.common.enums import VerificationResult


class AttestationVerifier:
    """Verifies signed runtime attestation claims."""

    NONCE_SEEN: ClassVar[set[str]] = set()
    MAX_CLOCK_SKEW_SECONDS = 300

    @classmethod
    def verify(
        cls,
        attestation_data: dict[str, Any],
        signature: str,
        public_key_pem: str,
        expected_agent_id: str,
    ) -> tuple[VerificationResult, str]:
        """Verify attestation claims and signature."""
        canonical = json.dumps(attestation_data, sort_keys=True)
        try:
            public_key = serialization.load_pem_public_key(public_key_pem.encode())
            if not isinstance(public_key, rsa.RSAPublicKey):
                return VerificationResult.REJECTED, "Unsupported public key type"
            public_key.verify(
                bytes.fromhex(signature),
                canonical.encode(),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except (InvalidSignature, ValueError) as exc:
            return VerificationResult.REJECTED, f"Signature verification failed: {exc}"

        issued_at_str = attestation_data.get("issued_at")
        if not issued_at_str:
            return VerificationResult.REJECTED, "Missing issued_at claim"

        try:
            issued_at = datetime.fromisoformat(issued_at_str.replace("Z", "+00:00"))
        except ValueError:
            return VerificationResult.REJECTED, "Invalid issued_at format"

        now = datetime.now(UTC)
        skew = abs((now - issued_at).total_seconds())
        if skew > cls.MAX_CLOCK_SKEW_SECONDS:
            return VerificationResult.REJECTED, f"Timestamp skew too large: {skew:.0f}s"

        nonce = attestation_data.get("nonce")
        if not nonce:
            return VerificationResult.REJECTED, "Missing nonce claim"
        if nonce in cls.NONCE_SEEN:
            return VerificationResult.REJECTED, f"Nonce already seen: {nonce}"
        cls.NONCE_SEEN.add(nonce)

        agent_id = attestation_data.get("agent_id")
        if agent_id != expected_agent_id:
            return (
                VerificationResult.REJECTED,
                f"Agent ID mismatch: {agent_id} != {expected_agent_id}",
            )

        required = [
            "container_digest",
            "git_commit",
            "environment",
            "host_id",
            "framework",
            "framework_version",
            "model",
            "prompt_version",
        ]
        missing = [claim for claim in required if claim not in attestation_data]
        if missing:
            return VerificationResult.REJECTED, f"Missing required claims: {missing}"

        return VerificationResult.VERIFIED, "All checks passed"

    @staticmethod
    def sign_attestation(claims: dict[str, Any], private_key_pem: str) -> str:
        """Sign attestation claims with private key and return a hex signature."""
        canonical = json.dumps(claims, sort_keys=True)
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
        )
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise ValueError("Unsupported private key type")
        signature = private_key.sign(
            canonical.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return signature.hex()
