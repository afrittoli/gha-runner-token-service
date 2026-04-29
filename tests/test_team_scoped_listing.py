"""Tests for team-scoped runner listing (Commit 3).

Covers:
- Individual users see own runners + team-mates' runners
- M2M tokens see only their team's runners
- Admins see all runners
- ?team= filter narrows results
"""

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.auth.token_types import TokenType
from app.models import Runner, Team, User, UserTeamMembership
from app.services.runner_service import RunnerService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_team(db: Session, name: str) -> Team:
    team = Team(
        name=name,
        required_labels=json.dumps([]),
        optional_label_patterns=json.dumps([]),
        is_active=True,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def _make_user(db: Session, email: str) -> User:
    user = User(email=email, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _add_to_team(db: Session, user: User, team: Team) -> None:
    m = UserTeamMembership(user_id=user.id, team_id=team.id)
    db.add(m)
    db.commit()


def _make_runner(
    db: Session,
    name: str,
    provisioned_by: "str | User",
    team: Team,
) -> Runner:
    # Accept either a User object (use its id) or a plain string
    pb = provisioned_by.id if isinstance(provisioned_by, User) else provisioned_by
    runner = Runner(
        runner_name=name,
        runner_group_id=1,
        labels=json.dumps(["self-hosted"]),
        provisioned_by=pb,
        team_id=team.id,
        team_name=team.name,
        github_url="https://github.com/test-org",
        status="active",
    )
    db.add(runner)
    db.commit()
    db.refresh(runner)
    return runner


def _make_settings():
    s = MagicMock()
    s.github_org = "test-org"
    s.github_app_id = "123"
    s.github_app_installation_id = "456"
    s.github_app_private_key_path = "/tmp/key.pem"
    return s


def _individual_user(
    db_user: User,
    claims: dict | None = None,
) -> AuthenticatedUser:
    return AuthenticatedUser(
        identity=db_user.id,
        claims=claims or {"email": db_user.email, "sub": f"sub|{db_user.id}"},
        token_type=TokenType.INDIVIDUAL,
        db_user=db_user,
    )


def _m2m_user(team: Team) -> AuthenticatedUser:
    return AuthenticatedUser(
        identity=f"m2m:{team.name}",
        claims={"sub": "client@clients", "team": team.name},
        token_type=TokenType.M2M_TEAM,
        team=team,
    )


def _admin_user(db_user: User) -> AuthenticatedUser:
    u = AuthenticatedUser(
        identity=db_user.id,
        claims={"email": db_user.email},
        token_type=TokenType.INDIVIDUAL,
        db_user=db_user,
    )
    u.is_admin = True
    return u


# ---------------------------------------------------------------------------
# RunnerService.list_runners unit tests
# ---------------------------------------------------------------------------


class TestListRunnersVisibility:
    """Unit tests for RunnerService.list_runners() visibility rules."""

    @pytest.mark.asyncio
    async def test_individual_sees_own_runners(self, test_db: Session):
        team = _make_team(test_db, "team-a")
        alice_db = _make_user(test_db, "alice@example.com")
        _add_to_team(test_db, alice_db, team)
        _make_runner(test_db, "alice-runner", alice_db, team)
        _make_runner(test_db, "other-runner", "bob@example.com", team)

        alice = _individual_user(alice_db)
        service = RunnerService(_make_settings(), test_db)
        runners = await service.list_runners(alice)

        names = {r.runner_name for r in runners}
        # Alice is in team-a → she sees both (own + team-mate)
        assert "alice-runner" in names
        assert "other-runner" in names

    @pytest.mark.asyncio
    async def test_individual_sees_team_runners(self, test_db: Session):
        team = _make_team(test_db, "shared-team")
        alice_db = _make_user(test_db, "alice2@example.com")
        bob_db = _make_user(test_db, "bob2@example.com")
        _add_to_team(test_db, alice_db, team)
        _add_to_team(test_db, bob_db, team)
        _make_runner(test_db, "bob-runner", "bob2@example.com", team)

        alice = _individual_user(alice_db)
        service = RunnerService(_make_settings(), test_db)
        runners = await service.list_runners(alice)

        assert any(r.runner_name == "bob-runner" for r in runners)

    @pytest.mark.asyncio
    async def test_individual_cannot_see_other_team_runners(self, test_db: Session):
        team_a = _make_team(test_db, "team-x")
        team_b = _make_team(test_db, "team-y")
        alice_db = _make_user(test_db, "alice3@example.com")
        _add_to_team(test_db, alice_db, team_a)
        _make_runner(test_db, "secret-runner", "bob3@example.com", team_b)

        alice = _individual_user(alice_db)
        service = RunnerService(_make_settings(), test_db)
        runners = await service.list_runners(alice)

        assert not any(r.runner_name == "secret-runner" for r in runners)

    @pytest.mark.asyncio
    async def test_m2m_sees_only_own_team(self, test_db: Session):
        team_a = _make_team(test_db, "m2m-team-a")
        team_b = _make_team(test_db, "m2m-team-b")
        _make_runner(test_db, "a-runner", "ci@clients", team_a)
        _make_runner(test_db, "b-runner", "ci@clients", team_b)

        m2m = _m2m_user(team_a)
        service = RunnerService(_make_settings(), test_db)
        runners = await service.list_runners(m2m)

        assert all(r.team_name == "m2m-team-a" for r in runners)
        assert not any(r.runner_name == "b-runner" for r in runners)

    @pytest.mark.asyncio
    async def test_admin_sees_all(self, test_db: Session):
        team_a = _make_team(test_db, "admin-team-a")
        team_b = _make_team(test_db, "admin-team-b")
        admin_db = _make_user(test_db, "admin@example.com")
        _make_runner(test_db, "runner-a", "x@example.com", team_a)
        _make_runner(test_db, "runner-b", "y@example.com", team_b)

        admin = _admin_user(admin_db)
        service = RunnerService(_make_settings(), test_db)
        runners = await service.list_runners(admin)

        names = {r.runner_name for r in runners}
        assert "runner-a" in names
        assert "runner-b" in names

    @pytest.mark.asyncio
    async def test_team_filter_for_admin(self, test_db: Session):
        team_a = _make_team(test_db, "filter-team-a")
        team_b = _make_team(test_db, "filter-team-b")
        admin_db = _make_user(test_db, "admin2@example.com")
        _make_runner(test_db, "ra", "x@example.com", team_a)
        _make_runner(test_db, "rb", "y@example.com", team_b)

        admin = _admin_user(admin_db)
        service = RunnerService(_make_settings(), test_db)
        runners = await service.list_runners(admin, team_name="filter-team-a")

        assert all(r.team_name == "filter-team-a" for r in runners)
        assert len(runners) == 1

    @pytest.mark.asyncio
    async def test_deleted_runners_excluded(self, test_db: Session):
        team = _make_team(test_db, "deleted-team")
        alice_db = _make_user(test_db, "alice4@example.com")
        _add_to_team(test_db, alice_db, team)
        r = _make_runner(test_db, "dead-runner", alice_db, team)
        r.status = "deleted"
        test_db.commit()

        alice = _individual_user(alice_db)
        service = RunnerService(_make_settings(), test_db)
        runners = await service.list_runners(alice)

        assert not any(r.runner_name == "dead-runner" for r in runners)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestListRunnersEndpoint:
    """API-level tests for GET /api/v1/runners."""

    def _setup_team_and_user(
        self,
        test_db: Session,
        email: str,
        team_name: str,
    ):
        team = _make_team(test_db, team_name)
        db_user = _make_user(test_db, email)
        _add_to_team(test_db, db_user, team)
        return team, db_user

    def test_list_returns_team_runners(
        self,
        client: TestClient,
        test_db: Session,
    ):
        from app.auth.dependencies import get_current_user
        from app.main import app

        team, db_user = self._setup_team_and_user(
            test_db, "list-user@example.com", "list-team"
        )
        runner = _make_runner(test_db, "team-runner", "other@example.com", team)

        auth_user = _individual_user(db_user)

        async def override():
            return auth_user

        app.dependency_overrides[get_current_user] = override
        try:
            response = client.get("/api/v1/runners")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        ids = [r["runner_id"] for r in data["runners"]]
        assert runner.id in ids

    def test_team_filter_param(
        self,
        client: TestClient,
        test_db: Session,
    ):
        from app.auth.dependencies import get_current_user
        from app.main import app

        team_a, alice_db = self._setup_team_and_user(
            test_db, "alice-ep@example.com", "ep-team-a"
        )
        team_b = _make_team(test_db, "ep-team-b")
        _add_to_team(test_db, alice_db, team_b)
        r_a = _make_runner(test_db, "ep-runner-a", "x@ep.com", team_a)
        _make_runner(test_db, "ep-runner-b", "y@ep.com", team_b)

        alice = _individual_user(alice_db)

        async def override():
            return alice

        app.dependency_overrides[get_current_user] = override
        try:
            response = client.get("/api/v1/runners?team=ep-team-a")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        ids = [r["runner_id"] for r in response.json()["runners"]]
        assert r_a.id in ids
        assert len(ids) == 1
