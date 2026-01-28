"""Unit tests for Team and UserTeamMembership models."""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models import Team, User, UserTeamMembership


def test_team_creation(test_db):
    """Test creating a team with required fields."""
    team = Team(
        name="backend-team",
        description="Backend development team",
        required_labels=json.dumps(["backend", "linux"]),
        optional_label_patterns=json.dumps(["backend-.*", "dev-.*"]),
        max_runners=20,
        created_by="admin@example.com",
    )
    test_db.add(team)
    test_db.commit()

    assert team.id is not None
    assert team.name == "backend-team"
    assert team.description == "Backend development team"
    assert team.is_active is True
    assert team.created_at is not None
    assert team.updated_at is not None
    assert team.deactivated_at is None


def test_team_unique_name(test_db):
    """Test that team names must be unique."""
    team1 = Team(
        name="backend-team",
        required_labels=json.dumps(["backend"]),
        created_by="admin@example.com",
    )
    test_db.add(team1)
    test_db.commit()

    # Try to create another team with the same name
    team2 = Team(
        name="backend-team",
        required_labels=json.dumps(["backend"]),
        created_by="admin@example.com",
    )
    test_db.add(team2)

    with pytest.raises(IntegrityError):
        test_db.commit()


def test_team_deactivation(test_db):
    """Test deactivating a team."""
    team = Team(
        name="backend-team",
        required_labels=json.dumps(["backend"]),
        created_by="admin@example.com",
    )
    test_db.add(team)
    test_db.commit()

    # Deactivate the team
    team.is_active = False
    team.deactivation_reason = "Team disbanded"
    team.deactivated_at = datetime.now(timezone.utc)
    team.deactivated_by = "admin@example.com"
    test_db.commit()

    assert team.is_active is False
    assert team.deactivation_reason == "Team disbanded"
    assert team.deactivated_at is not None
    assert team.deactivated_by == "admin@example.com"


def test_team_label_policy(test_db):
    """Test team label policy fields."""
    required = ["backend", "linux", "self-hosted"]
    optional_patterns = ["backend-.*", "dev-.*", "staging-.*"]

    team = Team(
        name="backend-team",
        required_labels=json.dumps(required),
        optional_label_patterns=json.dumps(optional_patterns),
        created_by="admin@example.com",
    )
    test_db.add(team)
    test_db.commit()

    # Verify JSON serialization
    assert json.loads(team.required_labels) == required
    assert json.loads(team.optional_label_patterns) == optional_patterns


def test_team_quota(test_db):
    """Test team quota field."""
    team = Team(
        name="backend-team",
        required_labels=json.dumps(["backend"]),
        max_runners=50,
        created_by="admin@example.com",
    )
    test_db.add(team)
    test_db.commit()

    assert team.max_runners == 50


def test_user_team_membership_creation(test_db):
    """Test creating a user-team membership."""
    # Create user
    user = User(
        email="user@example.com",
        oidc_sub="user123",
        is_admin=False,
    )
    test_db.add(user)

    # Create team
    team = Team(
        name="backend-team",
        required_labels=json.dumps(["backend"]),
        created_by="admin@example.com",
    )
    test_db.add(team)
    test_db.commit()

    # Create membership
    membership = UserTeamMembership(
        user_id=user.id,
        team_id=team.id,
        added_by="admin@example.com",
    )
    test_db.add(membership)
    test_db.commit()

    assert membership.id is not None
    assert membership.user_id == user.id
    assert membership.team_id == team.id
    assert membership.joined_at is not None
    assert membership.added_by == "admin@example.com"


def test_user_team_membership_unique_constraint(test_db):
    """Test that a user can only be added to a team once."""
    # Create user and team
    user = User(email="user@example.com", oidc_sub="user123")
    team = Team(
        name="backend-team",
        required_labels=json.dumps(["backend"]),
    )
    test_db.add(user)
    test_db.add(team)
    test_db.commit()

    # Create first membership
    membership1 = UserTeamMembership(
        user_id=user.id,
        team_id=team.id,
    )
    test_db.add(membership1)
    test_db.commit()

    # Try to create duplicate membership
    membership2 = UserTeamMembership(
        user_id=user.id,
        team_id=team.id,
    )
    test_db.add(membership2)

    with pytest.raises(IntegrityError):
        test_db.commit()


def test_user_multiple_teams(test_db):
    """Test that a user can belong to multiple teams."""
    # Create user
    user = User(email="user@example.com", oidc_sub="user123")
    test_db.add(user)

    # Create multiple teams
    team1 = Team(
        name="backend-team",
        required_labels=json.dumps(["backend"]),
    )
    team2 = Team(
        name="frontend-team",
        required_labels=json.dumps(["frontend"]),
    )
    test_db.add(team1)
    test_db.add(team2)
    test_db.commit()

    # Add user to both teams
    membership1 = UserTeamMembership(user_id=user.id, team_id=team1.id)
    membership2 = UserTeamMembership(user_id=user.id, team_id=team2.id)
    test_db.add(membership1)
    test_db.add(membership2)
    test_db.commit()

    # Query memberships
    memberships = test_db.query(UserTeamMembership).filter_by(user_id=user.id).all()
    assert len(memberships) == 2


def test_team_multiple_users(test_db):
    """Test that a team can have multiple users."""
    # Create team
    team = Team(
        name="backend-team",
        required_labels=json.dumps(["backend"]),
    )
    test_db.add(team)

    # Create multiple users
    user1 = User(email="user1@example.com", oidc_sub="user1")
    user2 = User(email="user2@example.com", oidc_sub="user2")
    test_db.add(user1)
    test_db.add(user2)
    test_db.commit()

    # Add both users to team
    membership1 = UserTeamMembership(user_id=user1.id, team_id=team.id)
    membership2 = UserTeamMembership(user_id=user2.id, team_id=team.id)
    test_db.add(membership1)
    test_db.add(membership2)
    test_db.commit()

    # Query memberships
    memberships = test_db.query(UserTeamMembership).filter_by(team_id=team.id).all()
    assert len(memberships) == 2


def test_cascade_delete_user(test_db):
    """Test that deleting a user cascades to memberships.

    Note: SQLite requires PRAGMA foreign_keys=ON for cascade deletes.
    This test verifies the model relationship is defined correctly.
    """
    # Enable foreign keys for SQLite
    test_db.execute(text("PRAGMA foreign_keys=ON"))

    # Create user and team
    user = User(email="user@example.com", oidc_sub="user123")
    team = Team(
        name="backend-team",
        required_labels=json.dumps(["backend"]),
    )
    test_db.add(user)
    test_db.add(team)
    test_db.commit()

    # Create membership
    membership = UserTeamMembership(user_id=user.id, team_id=team.id)
    test_db.add(membership)
    test_db.commit()

    membership_id = membership.id

    # Delete user
    test_db.delete(user)
    test_db.commit()

    # Verify membership is also deleted
    deleted_membership = (
        test_db.query(UserTeamMembership).filter_by(id=membership_id).first()
    )
    assert deleted_membership is None


def test_cascade_delete_team(test_db):
    """Test that deleting a team cascades to memberships.

    Note: SQLite requires PRAGMA foreign_keys=ON for cascade deletes.
    This test verifies the model relationship is defined correctly.
    """
    # Enable foreign keys for SQLite
    test_db.execute(text("PRAGMA foreign_keys=ON"))

    # Create user and team
    user = User(email="user@example.com", oidc_sub="user123")
    team = Team(
        name="backend-team",
        required_labels=json.dumps(["backend"]),
    )
    test_db.add(user)
    test_db.add(team)
    test_db.commit()

    # Create membership
    membership = UserTeamMembership(user_id=user.id, team_id=team.id)
    test_db.add(membership)
    test_db.commit()

    membership_id = membership.id

    # Delete team
    test_db.delete(team)
    test_db.commit()

    # Verify membership is also deleted
    deleted_membership = (
        test_db.query(UserTeamMembership).filter_by(id=membership_id).first()
    )
    assert deleted_membership is None
