"""Tests for OAuth M2M client admin API and OAuthClient model."""

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.oauth_clients import record_m2m_usage
from app.models import OAuthClient, Team


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_team(db: Session, name: str = "platform-team") -> Team:
    team = Team(
        name=name,
        required_labels=json.dumps(["self-hosted"]),
        optional_label_patterns=json.dumps([]),
        is_active=True,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def _make_client(
    db: Session,
    team: Team,
    client_id: str = "client@clients",
    is_active: bool = True,
) -> OAuthClient:
    c = OAuthClient(
        client_id=client_id,
        team_id=team.id,
        description="CI pipeline",
        is_active=is_active,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# CRUD endpoint tests (admin)
# ---------------------------------------------------------------------------


class TestOAuthClientCreate:
    def test_create_client_success(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        response = client.post(
            "/api/v1/admin/oauth-clients",
            json={
                "client_id": "ci-pipeline",
                "team_id": team.id,
                "description": "My CI pipeline",
            },
        )
        assert response.status_code == 201
        data = response.json()
        # Response is now {client: {...}, api_key: "gharts_..."}
        assert "api_key" in data
        assert data["api_key"].startswith("gharts_")
        assert data["client"]["client_id"] == "ci-pipeline"
        assert data["client"]["team_id"] == team.id
        assert data["client"]["description"] == "My CI pipeline"
        assert data["client"]["is_active"] is True

    def test_create_client_api_key_stored_as_hash(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        """The raw key must not be persisted; only the bcrypt hash is stored."""
        team = _make_team(test_db)
        response = client.post(
            "/api/v1/admin/oauth-clients",
            json={"client_id": "hash-check", "team_id": team.id},
        )
        assert response.status_code == 201
        raw_key = response.json()["api_key"]
        record_id = response.json()["client"]["id"]

        row = test_db.query(OAuthClient).filter(OAuthClient.id == record_id).first()
        assert row is not None
        assert row.hashed_key is not None
        # Raw key must not be stored in the hash column
        assert row.hashed_key != raw_key
        # Hash must start with bcrypt sentinel
        assert row.hashed_key.startswith("$2")

    def test_create_client_unknown_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        response = client.post(
            "/api/v1/admin/oauth-clients",
            json={"client_id": "ci-pipeline", "team_id": "nonexistent-uuid"},
        )
        assert response.status_code == 404

    def test_create_client_duplicate(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        _make_client(test_db, team, client_id="dup-client")
        response = client.post(
            "/api/v1/admin/oauth-clients",
            json={"client_id": "dup-client", "team_id": team.id},
        )
        assert response.status_code == 409

    def test_create_second_active_client_for_same_team_rejected(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        """A team may have only one active machine member at a time."""
        team = _make_team(test_db)
        _make_client(test_db, team, client_id="first-client")
        response = client.post(
            "/api/v1/admin/oauth-clients",
            json={"client_id": "second-client", "team_id": team.id},
        )
        assert response.status_code == 409
        assert "already has an active M2M client" in response.json()["detail"]

    def test_create_client_allowed_when_existing_is_inactive(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        """After disabling the old client a new one can be registered."""
        team = _make_team(test_db)
        _make_client(test_db, team, client_id="old-client", is_active=False)
        response = client.post(
            "/api/v1/admin/oauth-clients",
            json={"client_id": "new-client", "team_id": team.id},
        )
        assert response.status_code == 201
        assert response.json()["client"]["client_id"] == "new-client"

    def test_create_client_requires_admin(
        self,
        client: TestClient,
        test_db: Session,
        auth_override,
    ):
        team = _make_team(test_db)
        response = client.post(
            "/api/v1/admin/oauth-clients",
            json={"client_id": "ci-pipeline", "team_id": team.id},
        )
        assert response.status_code == 403


class TestOAuthClientList:
    def test_list_all(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        _make_client(test_db, team, "client-one")
        _make_client(test_db, team, "client-two")
        response = client.get("/api/v1/admin/oauth-clients")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["clients"]) == 2

    def test_list_filter_by_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team_a = _make_team(test_db, "team-a")
        team_b = _make_team(test_db, "team-b")
        _make_client(test_db, team_a, "client-a")
        _make_client(test_db, team_b, "client-b")
        response = client.get(f"/api/v1/admin/oauth-clients?team_id={team_a.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["clients"][0]["client_id"] == "client-a"

    def test_list_active_only_default(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        _make_client(test_db, team, "active-client", is_active=True)
        _make_client(test_db, team, "inactive-client", is_active=False)
        response = client.get("/api/v1/admin/oauth-clients")
        data = response.json()
        assert data["total"] == 1
        assert data["clients"][0]["client_id"] == "active-client"

    def test_list_include_inactive(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        _make_client(test_db, team, "active-client", is_active=True)
        _make_client(test_db, team, "inactive-client", is_active=False)
        response = client.get("/api/v1/admin/oauth-clients?active_only=false")
        data = response.json()
        assert data["total"] == 2


class TestOAuthClientRotate:
    def test_rotate_returns_new_key(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        """rotate endpoint returns a new gharts_ key and updates the hash."""
        team = _make_team(test_db)
        row = _make_client(test_db, team, "rotate-me")
        # Give it an initial hash so we can verify it changed
        from app.auth.api_keys import generate_api_key

        _, initial_hash = generate_api_key()
        row.hashed_key = initial_hash
        test_db.commit()

        response = client.post(f"/api/v1/admin/oauth-clients/{row.id}/rotate")
        assert response.status_code == 200
        data = response.json()
        assert data["api_key"].startswith("gharts_")
        assert data["client"]["id"] == row.id

        test_db.refresh(row)
        assert row.hashed_key != initial_hash

    def test_rotate_invalidates_old_key(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        """After rotation the old hash no longer matches the new raw key."""
        from app.auth.api_keys import generate_api_key, verify_api_key

        team = _make_team(test_db)
        row = _make_client(test_db, team, "invalidate-me")
        old_raw, old_hash = generate_api_key()
        row.hashed_key = old_hash
        test_db.commit()

        response = client.post(f"/api/v1/admin/oauth-clients/{row.id}/rotate")
        new_raw = response.json()["api_key"]

        test_db.refresh(row)
        # New raw key must verify against new hash
        assert verify_api_key(new_raw, row.hashed_key)
        # Old raw key must NOT verify against new hash
        assert not verify_api_key(old_raw, row.hashed_key)

    def test_rotate_not_found(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        response = client.post("/api/v1/admin/oauth-clients/no-such-id/rotate")
        assert response.status_code == 404


class TestOAuthClientUpdate:
    def test_update_description(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        c = _make_client(test_db, team)
        response = client.patch(
            f"/api/v1/admin/oauth-clients/{c.id}",
            json={"description": "updated desc"},
        )
        assert response.status_code == 200
        assert response.json()["description"] == "updated desc"

    def test_deactivate_client(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        c = _make_client(test_db, team)
        response = client.patch(
            f"/api/v1/admin/oauth-clients/{c.id}",
            json={"is_active": False},
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_update_not_found(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        response = client.patch(
            "/api/v1/admin/oauth-clients/no-such-id",
            json={"description": "x"},
        )
        assert response.status_code == 404


class TestOAuthClientDelete:
    def test_delete_client(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        c = _make_client(test_db, team)
        response = client.delete(f"/api/v1/admin/oauth-clients/{c.id}")
        assert response.status_code == 204
        assert test_db.query(OAuthClient).filter(OAuthClient.id == c.id).first() is None

    def test_delete_not_found(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        response = client.delete("/api/v1/admin/oauth-clients/no-such-id")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# record_m2m_usage
# ---------------------------------------------------------------------------


class TestRecordM2mUsage:
    def test_updates_last_used_at(self, test_db: Session):
        team = _make_team(test_db)
        c = _make_client(test_db, team, client_id="track@clients")
        assert c.last_used_at is None

        record_m2m_usage(test_db, "track@clients")

        test_db.refresh(c)
        assert c.last_used_at is not None

    def test_unknown_client_id_is_noop(self, test_db: Session):
        """record_m2m_usage is called after the client has been validated, so an
        unknown sub arriving here is a programming error. The function is still
        defensive and does not raise."""
        record_m2m_usage(test_db, "ghost@clients")  # must not raise

    def test_empty_client_id_is_noop(self, test_db: Session):
        record_m2m_usage(test_db, "")  # must not raise
