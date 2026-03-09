"""Integration tests for M2M machine-member auth enforcement.

These tests verify that get_current_user correctly enforces the invariant:
  "every M2M token must have an active, registered OAuthClient for its team."

The tests mock OIDC validation so they exercise the dependency logic without
needing a real JWT from Auth0.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import OAuthClient, Team


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_team(db: Session, name: str = "ci-team", active: bool = True) -> Team:
    team = Team(
        name=name,
        required_labels=json.dumps(["self-hosted"]),
        optional_label_patterns=json.dumps([]),
        is_active=active,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def _make_oauth_client(
    db: Session,
    team: Team,
    client_id: str = "pipeline@clients",
    is_active: bool = True,
) -> OAuthClient:
    c = OAuthClient(
        client_id=client_id,
        team_id=team.id,
        description="test pipeline",
        is_active=is_active,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _m2m_claims(team_name: str, sub: str = "pipeline@clients") -> dict:
    """Return a minimal M2M JWT payload."""
    return {
        "sub": sub,
        "team": team_name,
        "aud": "test-audience",
        "iss": "https://test-issuer.example.com/",
        "exp": 9999999999,
    }


# ---------------------------------------------------------------------------
# Fixture: patch OIDC validation so we control the claims
# ---------------------------------------------------------------------------

_PATCH_TARGET = "app.auth.dependencies.OIDCValidator.validate_token"
_AUTH_HEADERS = {"Authorization": "Bearer fake-token"}


@pytest.fixture
def m2m_client(client: TestClient):
    """
    Fixture that provides a helper to set the M2M claims returned by the
    mocked OIDC validator for the duration of the test.

    Usage:
        def test_foo(m2m_client):
            set_claims, tc = m2m_client
            set_claims({"sub": "x@clients", "team": "my-team"})
            tc.get("/api/v1/runners", headers={"Authorization": "Bearer fake"})
    """
    mock_validator = AsyncMock(return_value={})

    with patch(_PATCH_TARGET, new=mock_validator):

        def set_claims(claims: dict) -> None:
            mock_validator.return_value = claims

        yield set_claims, client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


_RUNNERS_URL = "/api/v1/runners"


class TestM2MAuthEnforcement:
    """Verify get_current_user blocks M2M tokens that are not registered."""

    def test_registered_active_client_succeeds(self, test_db: Session, m2m_client):
        """A properly registered and active client can authenticate."""
        team = _make_team(test_db, "ci-team")
        _make_oauth_client(test_db, team, client_id="pipeline@clients")

        set_claims, tc = m2m_client
        set_claims(_m2m_claims("ci-team", sub="pipeline@clients"))

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        # 200 means authentication succeeded (runner list may be empty)
        assert response.status_code == 200

    def test_unregistered_client_rejected(self, test_db: Session, m2m_client):
        """A token whose sub is not in oauth_clients is rejected (403)."""
        _make_team(test_db, "ci-team")
        # No OAuthClient row created — sub is unregistered

        set_claims, tc = m2m_client
        set_claims(_m2m_claims("ci-team", sub="ghost@clients"))

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "not registered" in detail
        assert "ghost@clients" in detail

    def test_disabled_client_rejected(self, test_db: Session, m2m_client):
        """A token whose OAuthClient row is is_active=False is rejected."""
        team = _make_team(test_db, "ci-team")
        _make_oauth_client(test_db, team, client_id="old@clients", is_active=False)

        set_claims, tc = m2m_client
        set_claims(_m2m_claims("ci-team", sub="old@clients"))

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "disabled" in detail.lower()

    def test_inactive_team_rejected(self, test_db: Session, m2m_client):
        """A token for a deactivated team is rejected even with a valid client."""
        team = _make_team(test_db, "frozen-team", active=False)
        _make_oauth_client(test_db, team, client_id="ci@clients")

        set_claims, tc = m2m_client
        set_claims(_m2m_claims("frozen-team", sub="ci@clients"))

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        assert response.status_code == 403
        assert "frozen-team" in response.json()["detail"]

    def test_unknown_team_rejected(self, test_db: Session, m2m_client):
        """A token whose team name is not in the DB is rejected."""
        set_claims, tc = m2m_client
        set_claims(_m2m_claims("no-such-team", sub="ci@clients"))

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        assert response.status_code == 403
        assert "no-such-team" in response.json()["detail"]

    def test_client_for_wrong_team_rejected(self, test_db: Session, m2m_client):
        """A client registered for team-A cannot authenticate as team-B."""
        team_a = _make_team(test_db, "team-a")
        _make_team(test_db, "team-b")
        # Register the client only for team-a
        _make_oauth_client(test_db, team_a, client_id="a@clients")

        # Token claims team-b but sub belongs to team-a
        set_claims, tc = m2m_client
        set_claims(_m2m_claims("team-b", sub="a@clients"))

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        assert response.status_code == 403
        assert "not registered" in response.json()["detail"]

    def test_last_used_at_updated_on_success(self, test_db: Session, m2m_client):
        """Successful M2M auth updates the OAuthClient.last_used_at field."""
        team = _make_team(test_db, "ci-team")
        oc = _make_oauth_client(test_db, team, client_id="pipeline@clients")
        assert oc.last_used_at is None

        set_claims, tc = m2m_client
        set_claims(_m2m_claims("ci-team", sub="pipeline@clients"))
        tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)

        test_db.refresh(oc)
        assert oc.last_used_at is not None
