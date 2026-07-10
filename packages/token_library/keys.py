"""Helpers for loading configured JWT keys with a test fallback."""

from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from packages.common.settings import Settings


@lru_cache(maxsize=1)
def _ephemeral_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def load_private_key(settings: Settings) -> str:
    if not settings.jwt_private_key_path:
        return _ephemeral_keypair()[0]
    with open(settings.jwt_private_key_path) as file:
        return file.read()


def load_public_key(settings: Settings) -> str:
    if not settings.jwt_public_key_path:
        return _ephemeral_keypair()[1]
    with open(settings.jwt_public_key_path) as file:
        return file.read()
