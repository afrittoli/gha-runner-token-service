"""Integration tests for M2M API-key authentication enforcement (Proposal B-1).

These tests verify that get_current_user correctly handles GHARTS-native
opaque API keys (``Bearer gharts_…``).  No JWT or Auth0 involvement.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.api_keys import generate_api_key
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
    client_id: str = "ci-pipeline",
    is_active: bool = True,
    with_key: bool = True,
):
    """Return (OAuthClient, raw_key).  raw_key is empty string when with_key=False."""
    raw_key = ""
    hashed_key = None
    if with_key:
        raw_key, hashed_key = generate_api_key()

    c = OAuthClient(
        client_id=client_id,
        hashed_key=hashed_key,
        team_id=team.id,
        description="test pipeline",
        is_active=is_active,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c, raw_key


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


_RUNNERS_URL = "/api/v1/runners"


class TestApiKeyAuthEnforcement:
    """Verify get_current_user handles GHARTS API keys correctly."""

    def test_valid_key_authenticates(self, test_db: Session, client: TestClient):
        """A valid gharts_ key for an active team succeeds (200)."""
        team = _make_team(test_db, "ci-team")
        _, raw_key = _make_oauth_client(test_db, team, "ci-pipeline")

        response = client.get(
            _RUNNERS_URL, headers={"Authorization": f"Bearer {raw_key}"}
        )
        assert response.status_code == 200

    def test_wrong_key_rejected(self, test_db: Session, client: TestClient):
        """A gharts_ key that doesn't match any stored hash is rejected (401)."""
        team = _make_team(test_db, "ci-team")
        _make_oauth_client(test_db, team, "ci-pipeline")

        # Different key — same prefix, different bytes
        wrong_raw, _ = generate_api_key()

        response = client.get(
            _RUNNERS_URL, headers={"Authorization": f"Bearer {wrong_raw}"}
        )
        assert response.status_code == 401

    def test_disabled_client_rejected(self, test_db: Session, client: TestClient):
        """A key belonging to a disabled client is rejected (401).

        Disabled clients are excluded from the candidate scan (is_active filter),
        so the key never matches → 401 rather than 403.
        """
        team = _make_team(test_db, "ci-team")
        _, raw_key = _make_oauth_client(
            test_db, team, "old-pipeline", is_active=False
        )

        response = client.get(
            _RUNNERS_URL, headers={"Authorization": f"Bearer {raw_key}"}
        )
        assert response.status_code == 401

    def test_inactive_team_rejected(self, test_db: Session, client: TestClient):
        """A valid key for a deactivated team is rejected (403)."""
        team = _make_team(test_db, "frozen-team", active=False)
        _, raw_key = _make_oauth_client(test_db, team, "ci-pipeline")

        response = client.get(
            _RUNNERS_URL, headers={"Authorization": f"Bearer {raw_key}"}
        )
        assert response.status_code == 403
        assert "inactive" in response.json()["detail"].lower()

    def test_client_without_hashed_key_not_matched(
        self, test_db: Session, client: TestClient
    ):
        """A client row with hashed_key=None is never matched (legacy row)."""
        team = _make_team(test_db, "ci-team")
        _make_oauth_client(test_db, team, "legacy-client", with_key=False)

        # Any gharts_ key will not match since the only row has no hash
        fake_raw, _ = generate_api_key()
        response = client.get(
            _RUNNERS_URL, headers={"Authorization": f"Bearer {fake_raw}"}
        )
        assert response.status_code == 401

    def test_last_used_at_updated_on_success(
        self, test_db: Session, client: TestClient
    ):
        """Successful API-key auth updates OAuthClient.last_used_at."""
        team = _make_team(test_db, "ci-team")
        row, raw_key = _make_oauth_client(test_db, team, "ci-pipeline")
        assert row.last_used_at is None

        client.get(_RUNNERS_URL, headers={"Authorization": f"Bearer {raw_key}"})

        test_db.refresh(row)
        assert row.last_used_at is not None

    def test_non_api_key_token_goes_to_jwt_path(
        self, test_db: Session, client: TestClient
    ):
        """Bearer tokens without gharts_ prefix are routed to the JWT path.

        We patch OIDC validation and create a matching user to confirm that
        the API-key branch does not intercept regular OIDC tokens.
        """
        from unittest.mock import AsyncMock, patch

        from app.models import User

        db_user = User(
            email="dev@example.com",
            oidc_sub="auth0|dev123",
            is_active=True,
            can_use_jit=True,
        )
        test_db.add(db_user)
        test_db.commit()

        with patch(
            "app.auth.dependencies.OIDCValidator.validate_token",
            new=AsyncMock(
                return_value={
                    "sub": "auth0|dev123",
                    "email": "dev@example.com",
                    "aud": "test-audience",
                    "iss": "https://test-issuer.example.com/",
                    "exp": 9999999999,
                }
            ),
        ):
            response = client.get(
                _RUNNERS_URL, headers={"Authorization": "Bearer some.jwt.token"}
            )
        assert response.status_code == 200
