import pytest

from apps.token_broker.providers.mock_oauth import MockOAuthProvider
from apps.token_broker.providers.static_secret import StaticSecretProvider


@pytest.mark.asyncio
async def test_mock_oauth_issues_token():
    provider = MockOAuthProvider()
    credential = await provider.issue("github", ["repo:read"], "ses_123")

    assert credential["type"] == "bearer"
    assert credential["token"].startswith("mock_oauth_token_")
    assert "expires_at" in credential


@pytest.mark.asyncio
async def test_static_secret_issues_token():
    provider = StaticSecretProvider()
    credential = await provider.issue("github", ["repo:read"], "ses_123")

    assert credential["token"] == "ghp_mock_secret_token"


@pytest.mark.asyncio
async def test_revoke_returns_true():
    provider = MockOAuthProvider()

    assert await provider.revoke("any") is True


@pytest.mark.asyncio
async def test_no_raw_secret_leakage():
    """Ensure the mock OAuth provider never emits a static raw secret token."""
    provider = MockOAuthProvider()
    credential = await provider.issue("github", ["admin"], "ses_123")

    assert credential["token"].startswith("mock_oauth_token_")
    assert credential["token"] != "ghp_mock_secret_token"
