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
                "client_id": "abc@clients",
                "team_id": team.id,
                "description": "My CI pipeline",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["client_id"] == "abc@clients"
        assert data["team_id"] == team.id
        assert data["description"] == "My CI pipeline"
        assert data["is_active"] is True

    def test_create_client_unknown_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        response = client.post(
            "/api/v1/admin/oauth-clients",
            json={"client_id": "abc@clients", "team_id": "nonexistent-uuid"},
        )
        assert response.status_code == 404

    def test_create_client_duplicate(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        _make_client(test_db, team, client_id="dup@clients")
        response = client.post(
            "/api/v1/admin/oauth-clients",
            json={"client_id": "dup@clients", "team_id": team.id},
        )
        assert response.status_code == 409

    def test_create_client_requires_admin(
        self,
        client: TestClient,
        test_db: Session,
        auth_override,
    ):
        team = _make_team(test_db)
        response = client.post(
            "/api/v1/admin/oauth-clients",
            json={"client_id": "abc@clients", "team_id": team.id},
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
        _make_client(test_db, team, "c1@clients")
        _make_client(test_db, team, "c2@clients")
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
        _make_client(test_db, team_a, "a@clients")
        _make_client(test_db, team_b, "b@clients")
        response = client.get(f"/api/v1/admin/oauth-clients?team_id={team_a.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["clients"][0]["client_id"] == "a@clients"

    def test_list_active_only_default(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        _make_client(test_db, team, "active@clients", is_active=True)
        _make_client(test_db, team, "inactive@clients", is_active=False)
        response = client.get("/api/v1/admin/oauth-clients")
        data = response.json()
        assert data["total"] == 1
        assert data["clients"][0]["client_id"] == "active@clients"

    def test_list_include_inactive(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override,
    ):
        team = _make_team(test_db)
        _make_client(test_db, team, "active@clients", is_active=True)
        _make_client(test_db, team, "inactive@clients", is_active=False)
        response = client.get("/api/v1/admin/oauth-clients?active_only=false")
        data = response.json()
        assert data["total"] == 2


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
        """Calling with an unregistered client_id should not raise."""
        record_m2m_usage(test_db, "ghost@clients")

    def test_empty_client_id_is_noop(self, test_db: Session):
        record_m2m_usage(test_db, "")
