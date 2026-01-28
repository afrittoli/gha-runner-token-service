"""Integration tests for team management API endpoints."""

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.models import Team, User, UserTeamMembership


class TestTeamManagementEndpoints:
    """Tests for team CRUD endpoints (admin-only)."""

    def test_create_team_success(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test creating a new team."""
        response = client.post(
            "/api/v1/teams",
            json={
                "name": "backend-team",
                "description": "Backend development team",
                "required_labels": ["backend", "python"],
                "optional_label_patterns": ["feature-.*", "bug-.*"],
                "max_runners": 10,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "backend-team"
        assert data["description"] == "Backend development team"
        assert data["required_labels"] == ["backend", "python"]
        assert data["optional_label_patterns"] == ["feature-.*", "bug-.*"]
        assert data["max_runners"] == 10
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

        # Verify in database
        team = test_db.query(Team).filter(Team.name == "backend-team").first()
        assert team is not None
        assert team.created_by == admin_auth_override.identity

    def test_create_team_duplicate_name(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test creating a team with duplicate name fails."""
        # Create first team
        team = Team(
            name="existing-team",
            required_labels=json.dumps(["test"]),
            created_by=admin_auth_override.identity,
        )
        test_db.add(team)
        test_db.commit()

        # Try to create duplicate
        response = client.post(
            "/api/v1/teams",
            json={
                "name": "existing-team",
                "required_labels": ["test"],
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_team_requires_admin(
        self, client: TestClient, test_db: Session, auth_override: AuthenticatedUser
    ):
        """Test that non-admin users cannot create teams."""
        response = client.post(
            "/api/v1/teams",
            json={
                "name": "test-team",
                "required_labels": ["test"],
            },
        )

        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]

    def test_list_teams(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test listing all teams."""
        # Create test teams
        teams = [
            Team(name="team-1", required_labels=json.dumps(["label1"]), is_active=True),
            Team(name="team-2", required_labels=json.dumps(["label2"]), is_active=True),
            Team(
                name="team-3",
                required_labels=json.dumps(["label3"]),
                is_active=False,
                deactivation_reason="Test deactivation",
            ),
        ]
        for team in teams:
            test_db.add(team)
        test_db.commit()

        # List active teams only (default)
        response = client.get("/api/v1/teams")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["teams"]) == 2
        assert all(t["is_active"] for t in data["teams"])

        # List all teams including inactive
        response = client.get("/api/v1/teams?include_inactive=true")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["teams"]) == 3

    def test_list_teams_pagination(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test team listing with pagination."""
        # Create 5 teams
        for i in range(5):
            team = Team(name=f"team-{i}", required_labels=json.dumps([f"label{i}"]))
            test_db.add(team)
        test_db.commit()

        # Get first page
        response = client.get("/api/v1/teams?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["teams"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0

        # Get second page
        response = client.get("/api/v1/teams?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["teams"]) == 2
        assert data["offset"] == 2

    def test_get_team_by_id(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test getting a team by ID."""
        team = Team(
            name="test-team",
            description="Test description",
            required_labels=json.dumps(["test"]),
            optional_label_patterns=json.dumps(["feature-.*"]),
            max_runners=5,
        )
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        response = client.get(f"/api/v1/teams/{team.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == team.id
        assert data["name"] == "test-team"
        assert data["description"] == "Test description"
        assert data["required_labels"] == ["test"]
        assert data["optional_label_patterns"] == ["feature-.*"]
        assert data["max_runners"] == 5

    def test_get_team_not_found(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test getting a non-existent team."""
        response = client.get("/api/v1/teams/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_update_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test updating a team."""
        team = Team(
            name="test-team",
            description="Old description",
            required_labels=json.dumps(["old"]),
            max_runners=5,
        )
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        response = client.patch(
            f"/api/v1/teams/{team.id}",
            json={
                "description": "New description",
                "required_labels": ["new", "updated"],
                "max_runners": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "New description"
        assert data["required_labels"] == ["new", "updated"]
        assert data["max_runners"] == 10
        assert data["name"] == "test-team"  # Name unchanged

    def test_update_team_partial(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test partial update of a team."""
        team = Team(
            name="test-team",
            description="Original",
            required_labels=json.dumps(["test"]),
            max_runners=5,
        )
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        # Update only description
        response = client.patch(
            f"/api/v1/teams/{team.id}",
            json={"description": "Updated description"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["required_labels"] == ["test"]  # Unchanged
        assert data["max_runners"] == 5  # Unchanged

    def test_deactivate_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test deactivating a team."""
        team = Team(name="test-team", required_labels=json.dumps(["test"]))
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        response = client.post(
            f"/api/v1/teams/{team.id}/deactivate",
            json={"reason": "Team no longer needed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
        assert data["deactivation_reason"] == "Team no longer needed"
        assert data["deactivated_by"] == admin_auth_override.identity
        assert "deactivated_at" in data

    def test_deactivate_already_inactive_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test deactivating an already inactive team."""
        team = Team(
            name="test-team",
            required_labels=json.dumps(["test"]),
            is_active=False,
            deactivation_reason="Already inactive",
        )
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        response = client.post(
            f"/api/v1/teams/{team.id}/deactivate",
            json={"reason": "Trying again"},
        )

        assert response.status_code == 400
        assert "already inactive" in response.json()["detail"]

    def test_reactivate_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test reactivating a team."""
        team = Team(
            name="test-team",
            required_labels=json.dumps(["test"]),
            is_active=False,
            deactivation_reason="Was deactivated",
        )
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        response = client.post(f"/api/v1/teams/{team.id}/reactivate")

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True
        assert data["deactivation_reason"] is None
        assert data["deactivated_by"] is None
        assert data["deactivated_at"] is None

    def test_reactivate_already_active_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test reactivating an already active team."""
        team = Team(
            name="test-team", required_labels=json.dumps(["test"]), is_active=True
        )
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        response = client.post(f"/api/v1/teams/{team.id}/reactivate")

        assert response.status_code == 400
        assert "already active" in response.json()["detail"]


class TestTeamMembershipEndpoints:
    """Tests for team membership endpoints (admin-only)."""

    def test_add_member_to_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test adding a user to a team."""
        # Create user and team
        user = User(email="user@example.com")
        team = Team(name="test-team", required_labels=json.dumps(["test"]))
        test_db.add(user)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(user)
        test_db.refresh(team)

        response = client.post(
            f"/api/v1/teams/{team.id}/members",
            json={"user_id": user.id},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == user.id
        assert data["team_id"] == team.id
        assert data["added_by"] == admin_auth_override.identity
        assert "joined_at" in data

        # Verify in database
        membership = (
            test_db.query(UserTeamMembership)
            .filter(
                UserTeamMembership.user_id == user.id,
                UserTeamMembership.team_id == team.id,
            )
            .first()
        )
        assert membership is not None

    def test_add_member_already_in_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test adding a user who is already in the team."""
        user = User(email="user@example.com")
        team = Team(name="test-team", required_labels=json.dumps(["test"]))
        test_db.add(user)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(user)
        test_db.refresh(team)

        # Add user to team
        membership = UserTeamMembership(user_id=user.id, team_id=team.id)
        test_db.add(membership)
        test_db.commit()

        # Try to add again
        response = client.post(
            f"/api/v1/teams/{team.id}/members",
            json={"user_id": user.id},
        )

        assert response.status_code == 400
        assert "already a member" in response.json()["detail"]

    def test_add_member_user_not_found(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test adding a non-existent user to a team."""
        team = Team(name="test-team", required_labels=json.dumps(["test"]))
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        response = client.post(
            f"/api/v1/teams/{team.id}/members",
            json={"user_id": "99999"},
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_add_member_team_not_found(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test adding a user to a non-existent team."""
        user = User(email="user@example.com")
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        response = client.post(
            "/api/v1/teams/99999/members",
            json={"user_id": user.id},
        )

        assert response.status_code == 404
        assert "Team not found" in response.json()["detail"]

    def test_list_team_members(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test listing members of a team."""
        # Create team and users
        team = Team(name="test-team", required_labels=json.dumps(["test"]))
        users = [User(email=f"user{i}@example.com") for i in range(3)]
        test_db.add(team)
        for user in users:
            test_db.add(user)
        test_db.commit()
        test_db.refresh(team)
        for user in users:
            test_db.refresh(user)

        # Add users to team
        for user in users:
            membership = UserTeamMembership(user_id=user.id, team_id=team.id)
            test_db.add(membership)
        test_db.commit()

        response = client.get(f"/api/v1/teams/{team.id}/members")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["members"]) == 3
        assert data["team_id"] == team.id

        # Verify member details
        member_emails = {m["user"]["email"] for m in data["members"]}
        assert member_emails == {
            "user0@example.com",
            "user1@example.com",
            "user2@example.com",
        }

    def test_list_team_members_empty(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test listing members of a team with no members."""
        team = Team(name="test-team", required_labels=json.dumps(["test"]))
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        response = client.get(f"/api/v1/teams/{team.id}/members")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["members"]) == 0

    def test_remove_member_from_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test removing a user from a team."""
        user = User(email="user@example.com")
        team = Team(name="test-team", required_labels=json.dumps(["test"]))
        test_db.add(user)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(user)
        test_db.refresh(team)

        # Add user to team
        membership = UserTeamMembership(user_id=user.id, team_id=team.id)
        test_db.add(membership)
        test_db.commit()

        response = client.delete(f"/api/v1/teams/{team.id}/members/{user.id}")

        assert response.status_code == 204

        # Verify removed from database
        membership = (
            test_db.query(UserTeamMembership)
            .filter(
                UserTeamMembership.user_id == user.id,
                UserTeamMembership.team_id == team.id,
            )
            .first()
        )
        assert membership is None

    def test_remove_member_not_in_team(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test removing a user who is not in the team."""
        user = User(email="user@example.com")
        team = Team(name="test-team", required_labels=json.dumps(["test"]))
        test_db.add(user)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(user)
        test_db.refresh(team)

        response = client.delete(f"/api/v1/teams/{team.id}/members/{user.id}")

        assert response.status_code == 404
        assert "not a member" in response.json()["detail"]

    def test_membership_requires_admin(
        self, client: TestClient, test_db: Session, auth_override: AuthenticatedUser
    ):
        """Test that non-admin users cannot manage team membership."""
        user = User(email="user@example.com")
        team = Team(name="test-team", required_labels=json.dumps(["test"]))
        test_db.add(user)
        test_db.add(team)
        test_db.commit()
        test_db.refresh(user)
        test_db.refresh(team)

        # Try to add member
        response = client.post(
            f"/api/v1/teams/{team.id}/members",
            json={"user_id": user.id},
        )
        assert response.status_code == 403

        # Try to list members
        response = client.get(f"/api/v1/teams/{team.id}/members")
        assert response.status_code == 403

        # Try to remove member
        response = client.delete(f"/api/v1/teams/{team.id}/members/{user.id}")
        assert response.status_code == 403


class TestUserTeamsEndpoint:
    """Tests for user teams endpoint (user can view own teams)."""

    def test_get_user_teams(
        self, client: TestClient, test_db: Session, auth_override: AuthenticatedUser
    ):
        """Test getting teams for a user."""
        # Create user
        user = User(email=auth_override.identity)
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        # Create teams
        teams = [
            Team(name="team-1", required_labels=json.dumps(["label1"])),
            Team(name="team-2", required_labels=json.dumps(["label2"])),
            Team(
                name="team-3",
                required_labels=json.dumps(["label3"]),
                is_active=False,
            ),
        ]
        for team in teams:
            test_db.add(team)
        test_db.commit()
        for team in teams:
            test_db.refresh(team)

        # Add user to teams
        for team in teams:
            membership = UserTeamMembership(user_id=user.id, team_id=team.id)
            test_db.add(membership)
        test_db.commit()

        response = client.get(f"/api/v1/teams/users/{user.id}/teams")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["teams"]) == 3
        assert data["user_id"] == user.id

        # Verify team details
        team_names = {t["name"] for t in data["teams"]}
        assert team_names == {"team-1", "team-2", "team-3"}

    def test_get_user_teams_empty(
        self, client: TestClient, test_db: Session, auth_override: AuthenticatedUser
    ):
        """Test getting teams for a user with no teams."""
        user = User(email=auth_override.identity)
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        response = client.get(f"/api/v1/teams/users/{user.id}/teams")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["teams"]) == 0

    def test_get_user_teams_user_not_found(
        self, client: TestClient, test_db: Session, auth_override: AuthenticatedUser
    ):
        """Test getting teams for a non-existent user."""
        response = client.get("/api/v1/teams/users/99999/teams")

        assert response.status_code == 403
        assert "view your own teams" in response.json()["detail"]

    def test_get_other_user_teams_forbidden(
        self, client: TestClient, test_db: Session, auth_override: AuthenticatedUser
    ):
        """Test that users cannot view other users' teams."""
        # Create another user
        other_user = User(email="other@example.com")
        test_db.add(other_user)
        test_db.commit()
        test_db.refresh(other_user)

        response = client.get(f"/api/v1/teams/users/{other_user.id}/teams")

        assert response.status_code == 403
        assert "view your own teams" in response.json()["detail"]

    def test_admin_can_view_any_user_teams(
        self,
        client: TestClient,
        test_db: Session,
        admin_auth_override: AuthenticatedUser,
    ):
        """Test that admins can view any user's teams."""
        # Create another user
        other_user = User(email="other@example.com")
        test_db.add(other_user)
        test_db.commit()
        test_db.refresh(other_user)

        # Create team and add user
        team = Team(name="test-team", required_labels=json.dumps(["test"]))
        test_db.add(team)
        test_db.commit()
        test_db.refresh(team)

        membership = UserTeamMembership(user_id=other_user.id, team_id=team.id)
        test_db.add(membership)
        test_db.commit()

        response = client.get(f"/api/v1/teams/users/{other_user.id}/teams")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["teams"][0]["name"] == "test-team"


# Made with Bob
