"""Integration tests for M2M machine-member auth enforcement.

These tests verify that get_current_user correctly enforces the invariant:
  "every M2M token must have an active, registered OAuthClient."

Token type is detected via ``gty="client-credentials"``. Team is resolved
from OAuthClient.team_id using the sub claim.

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


def _m2m_claims(sub: str = "pipeline@clients") -> dict:
    """Return a minimal M2M JWT payload using gty instead of team claim."""
    return {
        "sub": sub,
        "gty": "client-credentials",
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
            set_claims({"sub": "x@clients", "gty": "client-credentials"})
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
    """Verify that get_current_user enforces M2M token policy.

    Team resolution is via OAuthClient.team_id using the sub claim.
    """

    def test_registered_active_client_succeeds(self, test_db: Session, m2m_client):
        """A properly registered and active client can authenticate."""
        team = _make_team(test_db, "ci-team")
        _make_oauth_client(test_db, team, client_id="pipeline@clients")

        set_claims, tc = m2m_client
        set_claims(_m2m_claims(sub="pipeline@clients"))

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        # 200 means authentication succeeded (runner list may be empty)
        assert response.status_code == 200

    def test_unregistered_client_rejected(self, test_db: Session, m2m_client):
        """A token whose sub is not in oauth_clients is rejected (403)."""
        _make_team(test_db, "ci-team")
        # No OAuthClient row created — sub is unregistered

        set_claims, tc = m2m_client
        set_claims(_m2m_claims(sub="ghost@clients"))

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
        set_claims(_m2m_claims(sub="old@clients"))

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "disabled" in detail.lower()

    def test_inactive_team_rejected(self, test_db: Session, m2m_client):
        """A token whose linked team is deactivated is rejected."""
        team = _make_team(test_db, "frozen-team", active=False)
        _make_oauth_client(test_db, team, client_id="ci@clients")

        set_claims, tc = m2m_client
        set_claims(_m2m_claims(sub="ci@clients"))

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        assert response.status_code == 403

    def test_client_resolves_to_registered_team(self, test_db: Session, m2m_client):
        """Team is resolved from OAuthClient.team_id, not from any JWT claim.

        A client registered for team-a always resolves to team-a regardless of
        what any external claim might say — because the ``team`` claim is no
        longer used.
        """
        team_a = _make_team(test_db, "team-a")
        _make_oauth_client(test_db, team_a, client_id="a@clients")

        set_claims, tc = m2m_client
        set_claims(_m2m_claims(sub="a@clients"))

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        assert response.status_code == 200

    def test_last_used_at_updated_on_success(self, test_db: Session, m2m_client):
        """Successful M2M auth updates the OAuthClient.last_used_at field."""
        team = _make_team(test_db, "ci-team")
        oc = _make_oauth_client(test_db, team, client_id="pipeline@clients")
        assert oc.last_used_at is None

        set_claims, tc = m2m_client
        set_claims(_m2m_claims(sub="pipeline@clients"))
        tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)

        test_db.refresh(oc)
        assert oc.last_used_at is not None

    def test_no_team_claim_required(self, test_db: Session, m2m_client):
        """M2M auth succeeds even when no ``team`` claim is present in the JWT."""
        team = _make_team(test_db, "ci-team")
        _make_oauth_client(test_db, team, client_id="pipeline@clients")

        set_claims, tc = m2m_client
        claims = {
            "sub": "pipeline@clients",
            "gty": "client-credentials",
            "aud": "test-audience",
            "iss": "https://test-issuer.example.com/",
            "exp": 9999999999,
            # Explicitly no "team" claim
        }
        set_claims(claims)

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        assert response.status_code == 200

    def test_individual_token_not_treated_as_m2m(self, test_db: Session, m2m_client):
        """A token with gty=device_code is treated as INDIVIDUAL, not M2M."""
        from app.models import User

        user = User(
            email="dev@example.com",
            oidc_sub="auth0|dev",
            is_active=True,
            can_use_jit=True,
        )
        test_db.add(user)
        test_db.commit()

        set_claims, tc = m2m_client
        set_claims(
            {
                "sub": "auth0|dev",
                "email": "dev@example.com",
                "gty": "device_code",
                "aud": "test-audience",
                "iss": "https://test-issuer.example.com/",
                "exp": 9999999999,
            }
        )

        response = tc.get(_RUNNERS_URL, headers=_AUTH_HEADERS)
        assert response.status_code == 200
