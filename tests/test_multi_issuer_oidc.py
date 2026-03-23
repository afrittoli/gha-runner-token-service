"""Unit tests for MultiIssuerValidator and OIDCValidator (Proposal B-2).

These tests verify:
- OIDCValidator can be constructed from settings or directly.
- MultiIssuerValidator routes tokens to the correct validator by iss.
- Unknown issuers are rejected with 401.
- Zitadel validator is optional (backward-compatible single-issuer mode).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.auth.oidc import MultiIssuerValidator, OIDCValidator
from app.config import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_settings(
    *,
    oidc_issuer: str = "https://auth0.example.com/",
    oidc_jwks_url: str = "https://auth0.example.com/.well-known/jwks.json",
    oidc_audience: str = "gharts",
    zitadel_issuer: str | None = None,
    zitadel_jwks_url: str | None = None,
) -> MagicMock:
    s = MagicMock(spec=Settings)
    s.oidc_issuer = oidc_issuer
    s.oidc_jwks_url = oidc_jwks_url
    s.oidc_audience = oidc_audience
    s.zitadel_issuer = zitadel_issuer
    s.zitadel_jwks_url = zitadel_jwks_url
    return s




# ---------------------------------------------------------------------------
# OIDCValidator.from_settings
# ---------------------------------------------------------------------------


class TestOIDCValidatorFromSettings:
    def test_constructs_from_settings(self):
        s = _mock_settings()
        v = OIDCValidator.from_settings(s)
        assert v.issuer == s.oidc_issuer
        assert v.jwks_url == s.oidc_jwks_url
        assert v.audience == s.oidc_audience

    def test_direct_construction(self):
        v = OIDCValidator(
            issuer="https://example.com/",
            jwks_url="https://example.com/jwks",
            audience="my-api",
        )
        assert v.issuer == "https://example.com/"
        assert v.audience == "my-api"


# ---------------------------------------------------------------------------
# MultiIssuerValidator.from_settings
# ---------------------------------------------------------------------------


class TestMultiIssuerValidatorFromSettings:
    def test_single_issuer_mode_no_zitadel(self):
        s = _mock_settings()
        mv = MultiIssuerValidator.from_settings(s)
        assert mv._zitadel is None
        assert mv._auth0.issuer == s.oidc_issuer

    def test_dual_issuer_mode_with_zitadel(self):
        s = _mock_settings(
            zitadel_issuer="https://your-org.zitadel.cloud",
            zitadel_jwks_url="https://your-org.zitadel.cloud/oauth/v2/keys",
        )
        mv = MultiIssuerValidator.from_settings(s)
        assert mv._zitadel is not None
        assert mv._zitadel.issuer == "https://your-org.zitadel.cloud"

    def test_zitadel_not_created_when_only_issuer_set(self):
        """Both zitadel_issuer and zitadel_jwks_url must be set."""
        s = _mock_settings(zitadel_issuer="https://your-org.zitadel.cloud")
        mv = MultiIssuerValidator.from_settings(s)
        assert mv._zitadel is None


# ---------------------------------------------------------------------------
# MultiIssuerValidator._peek_issuer
# ---------------------------------------------------------------------------


class TestPeekIssuer:
    def test_rejects_malformed_token(self):
        s = _mock_settings()
        mv = MultiIssuerValidator.from_settings(s)
        with pytest.raises(HTTPException) as exc_info:
            mv._peek_issuer("not-a-jwt")
        assert exc_info.value.status_code == 401

    def test_rejects_token_without_iss(self):
        import base64
        import json

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS256", "typ": "JWT", "kid": "k1"}).encode()
        ).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "abc"}).encode()
        ).rstrip(b"=").decode()
        token = f"{header}.{payload}.fakesig"

        s = _mock_settings()
        mv = MultiIssuerValidator.from_settings(s)
        with pytest.raises(HTTPException) as exc_info:
            mv._peek_issuer(token)
        assert exc_info.value.status_code == 401
        assert "iss" in exc_info.value.detail


# ---------------------------------------------------------------------------
# MultiIssuerValidator._select_validator
# ---------------------------------------------------------------------------


class TestSelectValidator:
    def _make_token_with_iss(self, iss: str) -> str:
        """Craft a token whose unverified iss claim is the given value."""
        import base64
        import json

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS256", "typ": "JWT", "kid": "k1"}).encode()
        ).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "abc", "iss": iss}).encode()
        ).rstrip(b"=").decode()
        return f"{header}.{payload}.fakesig"

    def test_routes_auth0_token_to_auth0_validator(self):
        s = _mock_settings(
            oidc_issuer="https://auth0.example.com/",
            zitadel_issuer="https://zitadel.example.com",
            zitadel_jwks_url="https://zitadel.example.com/keys",
        )
        mv = MultiIssuerValidator.from_settings(s)
        token = self._make_token_with_iss("https://auth0.example.com/")
        selected = mv._select_validator(token)
        assert selected is mv._auth0

    def test_routes_zitadel_token_to_zitadel_validator(self):
        s = _mock_settings(
            oidc_issuer="https://auth0.example.com/",
            zitadel_issuer="https://zitadel.example.com",
            zitadel_jwks_url="https://zitadel.example.com/keys",
        )
        mv = MultiIssuerValidator.from_settings(s)
        token = self._make_token_with_iss("https://zitadel.example.com")
        selected = mv._select_validator(token)
        assert selected is mv._zitadel

    def test_unknown_issuer_raises_401(self):
        s = _mock_settings(oidc_issuer="https://auth0.example.com/")
        mv = MultiIssuerValidator.from_settings(s)
        token = self._make_token_with_iss("https://evil.example.com/")
        with pytest.raises(HTTPException) as exc_info:
            mv._select_validator(token)
        assert exc_info.value.status_code == 401
        assert "not trusted" in exc_info.value.detail

    def test_zitadel_issuer_not_accepted_when_not_configured(self):
        """In single-issuer mode, Zitadel tokens must be rejected."""
        s = _mock_settings(oidc_issuer="https://auth0.example.com/")
        mv = MultiIssuerValidator.from_settings(s)
        token = self._make_token_with_iss("https://your-org.zitadel.cloud")
        with pytest.raises(HTTPException) as exc_info:
            mv._select_validator(token)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# MultiIssuerValidator.validate_token (routing integration)
# ---------------------------------------------------------------------------


class TestMultiIssuerValidateToken:
    """Verify validate_token delegates to the correct per-issuer validator."""

    def _make_token_with_iss(self, iss: str) -> str:
        import base64
        import json

        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS256", "typ": "JWT", "kid": "k1"}).encode()
        ).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps({"sub": "abc", "iss": iss}).encode()
        ).rstrip(b"=").decode()
        return f"{header}.{payload}.fakesig"

    @pytest.mark.asyncio
    async def test_auth0_token_delegated_to_auth0_validator(self):
        auth0_issuer = "https://auth0.example.com/"
        s = _mock_settings(oidc_issuer=auth0_issuer)
        mv = MultiIssuerValidator.from_settings(s)

        expected_payload = {"sub": "user1", "iss": auth0_issuer}
        mv._auth0.validate_token = AsyncMock(return_value=expected_payload)

        token = self._make_token_with_iss(auth0_issuer)
        result = await mv.validate_token(token)
        assert result == expected_payload
        mv._auth0.validate_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_zitadel_token_delegated_to_zitadel_validator(self):
        zitadel_issuer = "https://your-org.zitadel.cloud"
        s = _mock_settings(
            oidc_issuer="https://auth0.example.com/",
            zitadel_issuer=zitadel_issuer,
            zitadel_jwks_url="https://your-org.zitadel.cloud/oauth/v2/keys",
        )
        mv = MultiIssuerValidator.from_settings(s)

        expected_payload = {
            "sub": "machine-user-id",
            "gty": "client-credentials",
            "iss": zitadel_issuer,
        }
        mv._zitadel.validate_token = AsyncMock(return_value=expected_payload)

        token = self._make_token_with_iss(zitadel_issuer)
        result = await mv.validate_token(token)
        assert result == expected_payload
        mv._zitadel.validate_token.assert_called_once_with(token)
