"""Tests for token type detection, API key utilities, and AuthenticatedUser."""

import json

import pytest
from sqlalchemy.orm import Session

from app.auth.api_keys import generate_api_key, is_api_key, verify_api_key
from app.auth.dependencies import AuthenticatedUser, _find_team_by_name
from app.auth.token_types import TokenType, detect_token_type
from app.models import Team


# ---------------------------------------------------------------------------
# detect_token_type  (JWT-only — M2M is handled pre-JWT by is_api_key())
# ---------------------------------------------------------------------------


class TestDetectTokenType:
    """Unit tests for detect_token_type()."""

    def test_individual_token_email_only(self):
        claims = {"sub": "auth0|123", "email": "dev@example.com"}
        assert detect_token_type(claims) == TokenType.INDIVIDUAL

    def test_individual_token_sub_only(self):
        claims = {"sub": "auth0|123"}
        assert detect_token_type(claims) == TokenType.INDIVIDUAL

    def test_individual_token_empty_claims(self):
        assert detect_token_type({}) == TokenType.INDIVIDUAL

    def test_impersonation_token(self):
        claims = {
            "is_impersonation": True,
            "email": "target@example.com",
            "impersonated_by": "admin@example.com",
        }
        assert detect_token_type(claims) == TokenType.IMPERSONATION

    def test_impersonation_takes_precedence(self):
        """Impersonation flag takes precedence over any other claims."""
        claims = {"is_impersonation": True, "sub": "auth0|123"}
        assert detect_token_type(claims) == TokenType.IMPERSONATION

    def test_false_impersonation_is_individual(self):
        claims = {"sub": "auth0|123", "is_impersonation": False}
        assert detect_token_type(claims) == TokenType.INDIVIDUAL

    def test_team_claim_no_longer_triggers_m2m(self):
        """The old Auth0 'team' claim is now ignored — M2M uses the API key path."""
        claims = {"sub": "auth0|123", "team": "platform-team"}
        assert detect_token_type(claims) == TokenType.INDIVIDUAL


# ---------------------------------------------------------------------------
# API key utilities
# ---------------------------------------------------------------------------


class TestApiKeyUtilities:
    """Unit tests for generate_api_key, verify_api_key, and is_api_key."""

    def test_generated_key_has_prefix(self):
        raw_key, _ = generate_api_key()
        assert raw_key.startswith("gharts_")

    def test_generated_key_has_sufficient_entropy(self):
        raw_key, _ = generate_api_key()
        # 32 bytes → 43 base64url chars (no padding) + 7 prefix
        assert len(raw_key) >= 40

    def test_generated_key_verifies_against_hash(self):
        raw_key, hashed = generate_api_key()
        assert verify_api_key(raw_key, hashed)

    def test_different_key_does_not_verify(self):
        raw_key, hashed = generate_api_key()
        other_key, _ = generate_api_key()
        assert not verify_api_key(other_key, hashed)

    def test_empty_key_does_not_verify(self):
        _, hashed = generate_api_key()
        assert not verify_api_key("", hashed)

    def test_empty_hash_does_not_verify(self):
        raw_key, _ = generate_api_key()
        assert not verify_api_key(raw_key, "")

    def test_is_api_key_true_for_gharts_prefix(self):
        raw_key, _ = generate_api_key()
        assert is_api_key(raw_key)

    def test_is_api_key_false_for_jwt(self):
        assert not is_api_key("eyJhbGciOiJSUzI1NiJ9.abc.def")

    def test_is_api_key_false_for_empty(self):
        assert not is_api_key("")

    def test_hash_stored_as_bcrypt(self):
        _, hashed = generate_api_key()
        # bcrypt hashes start with $2b$ or $2a$
        assert hashed.startswith("$2")

    def test_two_keys_produce_unique_values(self):
        raw1, hash1 = generate_api_key()
        raw2, hash2 = generate_api_key()
        assert raw1 != raw2
        assert hash1 != hash2


# ---------------------------------------------------------------------------
# AuthenticatedUser construction
# ---------------------------------------------------------------------------


class TestAuthenticatedUserIndividual:
    """Tests for AuthenticatedUser in INDIVIDUAL mode."""

    def test_defaults_to_individual(self):
        user = AuthenticatedUser(
            identity="dev@example.com",
            claims={"sub": "auth0|123", "email": "dev@example.com"},
        )
        assert user.token_type == TokenType.INDIVIDUAL

    def test_no_team_context(self):
        user = AuthenticatedUser(
            identity="dev@example.com",
            claims={"sub": "auth0|123", "email": "dev@example.com"},
        )
        assert user.team is None
        assert user.team_name_from_token is None

    def test_without_db_user_no_api_access(self):
        """Individual token without a db_user should not get API access."""
        user = AuthenticatedUser(
            identity="dev@example.com",
            claims={"sub": "auth0|123", "email": "dev@example.com"},
            token_type=TokenType.INDIVIDUAL,
        )
        assert not user.can_use_jit

    def test_with_db_user_inherits_permissions(self, mock_db_user):
        user = AuthenticatedUser(
            identity="dev@example.com",
            claims={"sub": "auth0|123", "email": "dev@example.com"},
            token_type=TokenType.INDIVIDUAL,
            db_user=mock_db_user,
        )
        assert user.can_use_jit == mock_db_user.can_use_jit
        assert user.is_admin == mock_db_user.is_admin

    def test_str_returns_identity(self):
        user = AuthenticatedUser(
            identity="dev@example.com",
            claims={"email": "dev@example.com"},
        )
        assert str(user) == "dev@example.com"


class TestAuthenticatedUserM2M:
    """Tests for AuthenticatedUser in M2M_TEAM mode (API key path)."""

    def _make_team(self):
        from unittest.mock import MagicMock

        team = MagicMock(spec=Team)
        team.id = "team-uuid-123"
        team.name = "platform-team"
        team.is_active = True
        return team

    def test_m2m_has_full_api_access(self):
        team = self._make_team()
        user = AuthenticatedUser(
            identity="m2m:platform-team",
            claims={"client_id": "ci-pipeline"},
            token_type=TokenType.M2M_TEAM,
            team=team,
        )
        assert user.can_use_jit is True

    def test_m2m_team_context_set(self):
        team = self._make_team()
        user = AuthenticatedUser(
            identity="m2m:platform-team",
            claims={"client_id": "ci-pipeline"},
            token_type=TokenType.M2M_TEAM,
            team=team,
        )
        assert user.team is team

    def test_m2m_not_admin(self):
        """M2M API keys must never grant admin privileges."""
        team = self._make_team()
        user = AuthenticatedUser(
            identity="m2m:platform-team",
            claims={"client_id": "ci-pipeline"},
            token_type=TokenType.M2M_TEAM,
            team=team,
        )
        assert user.is_admin is False

    def test_m2m_no_db_user(self):
        team = self._make_team()
        user = AuthenticatedUser(
            identity="m2m:platform-team",
            claims={"client_id": "ci-pipeline"},
            token_type=TokenType.M2M_TEAM,
            team=team,
        )
        assert user.db_user is None
        assert user.user_id is None

    def test_m2m_identity_format(self):
        team = self._make_team()
        user = AuthenticatedUser(
            identity="m2m:platform-team",
            claims={"client_id": "ci-pipeline"},
            token_type=TokenType.M2M_TEAM,
            team=team,
        )
        assert str(user) == "m2m:platform-team"


# ---------------------------------------------------------------------------
# _find_team_by_name
# ---------------------------------------------------------------------------


class TestFindTeamByName:
    """Integration tests for _find_team_by_name()."""

    def test_finds_active_team(self, test_db: Session, test_team: Team):
        found = _find_team_by_name(test_db, test_team.name)
        assert found is not None
        assert found.id == test_team.id

    def test_returns_none_for_unknown_team(self, test_db: Session):
        assert _find_team_by_name(test_db, "no-such-team") is None

    def test_returns_none_for_inactive_team(self, test_db: Session):
        team = Team(
            name="inactive-team",
            required_labels=json.dumps([]),
            is_active=False,
        )
        test_db.add(team)
        test_db.commit()

        assert _find_team_by_name(test_db, "inactive-team") is None

    def test_finds_by_exact_name(self, test_db: Session, test_team: Team):
        # Partial name should not match
        partial = test_team.name[:-1]
        assert _find_team_by_name(test_db, partial) is None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_user():
    """Minimal mock User object."""
    from unittest.mock import MagicMock

    user = MagicMock()
    user.id = "user-uuid-456"
    user.is_admin = False
    user.is_active = True
    user.can_use_jit = True
    user.display_name = "Test Developer"
    return user
