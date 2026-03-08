"""Tests for token type detection and M2M AuthenticatedUser construction."""

import json

import pytest
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser, _find_team_by_name
from app.auth.token_types import TokenType, detect_token_type
from app.models import Team


# ---------------------------------------------------------------------------
# detect_token_type
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

    def test_m2m_team_token(self):
        claims = {
            "sub": "client@clients",
            "team": "platform-team",
            "aud": "gharts",
        }
        assert detect_token_type(claims) == TokenType.M2M_TEAM

    def test_m2m_team_token_no_email(self):
        """M2M tokens from client_credentials have no email claim."""
        claims = {"sub": "service-account@clients", "team": "infra"}
        assert detect_token_type(claims) == TokenType.M2M_TEAM

    def test_impersonation_token(self):
        claims = {
            "is_impersonation": True,
            "email": "target@example.com",
            "impersonated_by": "admin@example.com",
        }
        assert detect_token_type(claims) == TokenType.IMPERSONATION

    def test_impersonation_takes_precedence_over_team(self):
        """Impersonation flag takes precedence even if team claim present."""
        claims = {"is_impersonation": True, "team": "some-team"}
        assert detect_token_type(claims) == TokenType.IMPERSONATION

    def test_empty_team_string_is_individual(self):
        """An empty team claim should not be treated as M2M."""
        claims = {"sub": "auth0|123", "team": ""}
        assert detect_token_type(claims) == TokenType.INDIVIDUAL

    def test_none_team_is_individual(self):
        """A None team claim should not be treated as M2M."""
        claims = {"sub": "auth0|123", "team": None}
        assert detect_token_type(claims) == TokenType.INDIVIDUAL

    def test_false_impersonation_is_individual(self):
        claims = {"sub": "auth0|123", "is_impersonation": False}
        assert detect_token_type(claims) == TokenType.INDIVIDUAL


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
        assert not user.can_use_registration_token
        assert not user.can_use_jit

    def test_with_db_user_inherits_permissions(self, mock_db_user):
        user = AuthenticatedUser(
            identity="dev@example.com",
            claims={"sub": "auth0|123", "email": "dev@example.com"},
            token_type=TokenType.INDIVIDUAL,
            db_user=mock_db_user,
        )
        assert user.can_use_registration_token == (
            mock_db_user.can_use_registration_token
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
    """Tests for AuthenticatedUser in M2M_TEAM mode."""

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
            claims={"sub": "client@clients", "team": "platform-team"},
            token_type=TokenType.M2M_TEAM,
            team=team,
        )
        assert user.can_use_registration_token is True
        assert user.can_use_jit is True

    def test_m2m_team_context_set(self):
        team = self._make_team()
        user = AuthenticatedUser(
            identity="m2m:platform-team",
            claims={"sub": "client@clients", "team": "platform-team"},
            token_type=TokenType.M2M_TEAM,
            team=team,
        )
        assert user.team is team
        assert user.team_name_from_token == "platform-team"

    def test_m2m_not_admin(self):
        """M2M tokens should never have admin privileges."""
        team = self._make_team()
        user = AuthenticatedUser(
            identity="m2m:platform-team",
            claims={"sub": "client@clients", "team": "platform-team"},
            token_type=TokenType.M2M_TEAM,
            team=team,
        )
        assert user.is_admin is False

    def test_m2m_no_db_user(self):
        team = self._make_team()
        user = AuthenticatedUser(
            identity="m2m:platform-team",
            claims={"sub": "client@clients", "team": "platform-team"},
            token_type=TokenType.M2M_TEAM,
            team=team,
        )
        assert user.db_user is None
        assert user.user_id is None

    def test_m2m_identity_format(self):
        team = self._make_team()
        user = AuthenticatedUser(
            identity="m2m:platform-team",
            claims={"sub": "client@clients", "team": "platform-team"},
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
    user.can_use_registration_token = True
    user.can_use_jit = True
    user.display_name = "Test Developer"
    return user
