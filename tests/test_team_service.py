"""Unit tests for team service."""

import json
import pytest
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Runner, Team, User
from app.services.team_service import TeamPolicyViolation, TeamService


@pytest.fixture
def team_service(test_db: Session) -> TeamService:
    """Create team service instance."""
    return TeamService(test_db)


@pytest.fixture
def sample_user(test_db: Session) -> User:
    """Create a sample user."""
    user = User(
        email="alice@example.com",
        oidc_sub="alice-sub",
        display_name="Alice",
        is_admin=False,
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def sample_team(test_db: Session) -> Team:
    """Create a sample team."""
    team = Team(
        name="platform-team",
        description="Platform engineering team",
        required_labels=json.dumps(["platform", "production"]),
        optional_label_patterns=json.dumps(["feature-.*", "env-.*"]),
        max_runners=10,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_db.add(team)
    test_db.commit()
    test_db.refresh(team)
    return team


class TestTeamCRUD:
    """Test team CRUD operations."""

    def test_create_team_success(self, team_service: TeamService):
        """Test creating a team successfully."""
        team = team_service.create_team(
            name="backend-team",
            required_labels=["backend", "api"],
            description="Backend development team",
            optional_label_patterns=["service-.*"],
            max_runners=5,
            created_by="admin@example.com",
        )

        assert team.name == "backend-team"
        assert team.description == "Backend development team"
        assert json.loads(team.required_labels) == ["backend", "api"]
        assert json.loads(team.optional_label_patterns) == ["service-.*"]
        assert team.max_runners == 5
        assert team.is_active is True
        assert team.created_by == "admin@example.com"

    def test_create_team_invalid_name(self, team_service: TeamService):
        """Test creating team with invalid name format."""
        with pytest.raises(ValueError, match="kebab-case"):
            team_service.create_team(
                name="Invalid_Name",
                required_labels=["test"],
            )

    def test_create_team_duplicate_name(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test creating team with duplicate name."""
        with pytest.raises(ValueError, match="already exists"):
            team_service.create_team(
                name=sample_team.name,
                required_labels=["test"],
            )

    def test_get_team(self, team_service: TeamService, sample_team: Team):
        """Test getting team by ID."""
        team = team_service.get_team(sample_team.id)
        assert team is not None
        assert team.id == sample_team.id
        assert team.name == sample_team.name

    def test_get_team_not_found(self, team_service: TeamService):
        """Test getting non-existent team."""
        team = team_service.get_team("non-existent-id")
        assert team is None

    def test_get_team_by_name(self, team_service: TeamService, sample_team: Team):
        """Test getting team by name."""
        team = team_service.get_team_by_name(sample_team.name)
        assert team is not None
        assert team.id == sample_team.id

    def test_list_teams(self, team_service: TeamService, sample_team: Team):
        """Test listing teams."""
        # Create another team
        team_service.create_team(
            name="frontend-team",
            required_labels=["frontend"],
        )

        teams = team_service.list_teams()
        assert len(teams) >= 2
        team_names = [t.name for t in teams]
        assert sample_team.name in team_names
        assert "frontend-team" in team_names

    def test_list_teams_exclude_inactive(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test listing teams excludes inactive by default."""
        # Deactivate sample team
        team_service.deactivate_team(
            sample_team.id,
            reason="Test deactivation",
            deactivated_by="admin@example.com",
        )

        teams = team_service.list_teams(include_inactive=False)
        team_ids = [t.id for t in teams]
        assert sample_team.id not in team_ids

    def test_list_teams_include_inactive(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test listing teams includes inactive when requested."""
        # Deactivate sample team
        team_service.deactivate_team(
            sample_team.id,
            reason="Test deactivation",
            deactivated_by="admin@example.com",
        )

        teams = team_service.list_teams(include_inactive=True)
        team_ids = [t.id for t in teams]
        assert sample_team.id in team_ids

    def test_update_team(self, team_service: TeamService, sample_team: Team):
        """Test updating team configuration."""
        updated_team = team_service.update_team(
            sample_team.id,
            description="Updated description",
            required_labels=["new-label"],
            max_runners=20,
        )

        assert updated_team.description == "Updated description"
        assert json.loads(updated_team.required_labels) == ["new-label"]
        assert updated_team.max_runners == 20

    def test_update_team_not_found(self, team_service: TeamService):
        """Test updating non-existent team."""
        with pytest.raises(ValueError, match="not found"):
            team_service.update_team(
                "non-existent-id",
                description="Test",
            )

    def test_deactivate_team(self, team_service: TeamService, sample_team: Team):
        """Test deactivating a team."""
        deactivated_team = team_service.deactivate_team(
            sample_team.id,
            reason="No longer needed",
            deactivated_by="admin@example.com",
        )

        assert deactivated_team.is_active is False
        assert deactivated_team.deactivation_reason == "No longer needed"
        assert deactivated_team.deactivated_by == "admin@example.com"
        assert deactivated_team.deactivated_at is not None

    def test_deactivate_team_already_inactive(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test deactivating already inactive team."""
        team_service.deactivate_team(
            sample_team.id,
            reason="First deactivation",
            deactivated_by="admin@example.com",
        )

        with pytest.raises(ValueError, match="already deactivated"):
            team_service.deactivate_team(
                sample_team.id,
                reason="Second deactivation",
                deactivated_by="admin@example.com",
            )

    def test_reactivate_team(self, team_service: TeamService, sample_team: Team):
        """Test reactivating a deactivated team."""
        # First deactivate
        team_service.deactivate_team(
            sample_team.id,
            reason="Test",
            deactivated_by="admin@example.com",
        )

        # Then reactivate
        reactivated_team = team_service.reactivate_team(sample_team.id)

        assert reactivated_team.is_active is True
        assert reactivated_team.deactivation_reason is None
        assert reactivated_team.deactivated_by is None
        assert reactivated_team.deactivated_at is None

    def test_reactivate_team_already_active(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test reactivating already active team."""
        with pytest.raises(ValueError, match="already active"):
            team_service.reactivate_team(sample_team.id)


class TestTeamMembership:
    """Test team membership operations."""

    def test_add_user_to_team(
        self,
        team_service: TeamService,
        sample_user: User,
        sample_team: Team,
    ):
        """Test adding user to team."""
        membership = team_service.add_user_to_team(
            sample_user.id,
            sample_team.id,
            added_by="admin@example.com",
        )

        assert membership.user_id == sample_user.id
        assert membership.team_id == sample_team.id
        assert membership.added_by == "admin@example.com"
        assert membership.joined_at is not None

    def test_add_user_to_team_duplicate(
        self,
        team_service: TeamService,
        sample_user: User,
        sample_team: Team,
    ):
        """Test adding user to team twice."""
        team_service.add_user_to_team(sample_user.id, sample_team.id)

        with pytest.raises(ValueError, match="already a member"):
            team_service.add_user_to_team(sample_user.id, sample_team.id)

    def test_add_user_to_team_user_not_found(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test adding non-existent user to team."""
        with pytest.raises(ValueError, match="User not found"):
            team_service.add_user_to_team("non-existent-id", sample_team.id)

    def test_add_user_to_team_team_not_found(
        self, team_service: TeamService, sample_user: User
    ):
        """Test adding user to non-existent team."""
        with pytest.raises(ValueError, match="Team not found"):
            team_service.add_user_to_team(sample_user.id, "non-existent-id")

    def test_remove_user_from_team(
        self,
        team_service: TeamService,
        sample_user: User,
        sample_team: Team,
    ):
        """Test removing user from team."""
        team_service.add_user_to_team(sample_user.id, sample_team.id)
        team_service.remove_user_from_team(sample_user.id, sample_team.id)

        # Verify membership is gone
        assert not team_service.is_user_in_team(sample_user.id, sample_team.id)

    def test_remove_user_from_team_not_member(
        self,
        team_service: TeamService,
        sample_user: User,
        sample_team: Team,
    ):
        """Test removing user who is not a member."""
        with pytest.raises(ValueError, match="not a member"):
            team_service.remove_user_from_team(sample_user.id, sample_team.id)

    def test_get_user_teams(
        self,
        team_service: TeamService,
        sample_user: User,
        sample_team: Team,
    ):
        """Test getting teams for a user."""
        # Create another team
        team2 = team_service.create_team(
            name="data-team",
            required_labels=["data"],
        )

        # Add user to both teams
        team_service.add_user_to_team(sample_user.id, sample_team.id)
        team_service.add_user_to_team(sample_user.id, team2.id)

        teams = team_service.get_user_teams(sample_user.id)
        assert len(teams) == 2
        team_ids = [t.id for t in teams]
        assert sample_team.id in team_ids
        assert team2.id in team_ids

    def test_get_user_teams_no_memberships(
        self, team_service: TeamService, sample_user: User
    ):
        """Test getting teams for user with no memberships."""
        teams = team_service.get_user_teams(sample_user.id)
        assert len(teams) == 0

    def test_get_team_members(
        self,
        team_service: TeamService,
        test_db: Session,
        sample_team: Team,
    ):
        """Test getting members of a team."""
        # Create users
        user1 = User(email="user1@example.com", is_active=True)
        user2 = User(email="user2@example.com", is_active=True)
        test_db.add_all([user1, user2])
        test_db.commit()

        # Add users to team
        team_service.add_user_to_team(user1.id, sample_team.id)
        team_service.add_user_to_team(user2.id, sample_team.id)

        members = team_service.get_team_members(sample_team.id)
        assert len(members) == 2
        member_emails = [m.email for m in members]
        assert "user1@example.com" in member_emails
        assert "user2@example.com" in member_emails

    def test_get_team_members_no_members(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test getting members of team with no members."""
        members = team_service.get_team_members(sample_team.id)
        assert len(members) == 0

    def test_is_user_in_team(
        self,
        team_service: TeamService,
        sample_user: User,
        sample_team: Team,
    ):
        """Test checking if user is in team."""
        assert not team_service.is_user_in_team(sample_user.id, sample_team.id)

        team_service.add_user_to_team(sample_user.id, sample_team.id)

        assert team_service.is_user_in_team(sample_user.id, sample_team.id)


class TestLabelPolicyEnforcement:
    """Test label policy enforcement."""

    def test_validate_and_merge_labels_success(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test validating and merging labels successfully."""
        optional_labels = ["feature-auth", "env-staging"]

        merged_labels, invalid_labels = team_service.validate_and_merge_labels(
            sample_team.id, optional_labels
        )

        # Should include required + valid optional labels
        assert "platform" in merged_labels
        assert "production" in merged_labels
        assert "feature-auth" in merged_labels
        assert "env-staging" in merged_labels
        assert len(invalid_labels) == 0

    def test_validate_and_merge_labels_no_optional(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test merging with no optional labels."""
        merged_labels, invalid_labels = team_service.validate_and_merge_labels(
            sample_team.id, []
        )

        # Should only include required labels
        assert merged_labels == ["platform", "production"]
        assert len(invalid_labels) == 0

    def test_validate_and_merge_labels_invalid(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test validation with invalid labels."""
        optional_labels = ["invalid-label", "feature-valid"]

        with pytest.raises(TeamPolicyViolation) as exc_info:
            team_service.validate_and_merge_labels(sample_team.id, optional_labels)

        assert "invalid-label" in exc_info.value.invalid_labels
        assert "feature-valid" not in exc_info.value.invalid_labels

    def test_validate_and_merge_labels_system_labels_allowed(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test that system labels are always allowed."""
        optional_labels = ["linux", "x64", "self-hosted"]

        merged_labels, invalid_labels = team_service.validate_and_merge_labels(
            sample_team.id, optional_labels
        )

        # System labels should not be validated against patterns
        assert len(invalid_labels) == 0

    def test_validate_and_merge_labels_team_not_found(self, team_service: TeamService):
        """Test validation with non-existent team."""
        with pytest.raises(ValueError, match="not found"):
            team_service.validate_and_merge_labels("non-existent-id", [])

    def test_validate_and_merge_labels_inactive_team(
        self, team_service: TeamService, sample_team: Team
    ):
        """Test validation with inactive team."""
        team_service.deactivate_team(
            sample_team.id,
            reason="Test",
            deactivated_by="admin@example.com",
        )

        with pytest.raises(ValueError, match="deactivated"):
            team_service.validate_and_merge_labels(sample_team.id, [])


class TestTeamQuota:
    """Test team quota enforcement."""

    def test_check_team_quota(
        self,
        team_service: TeamService,
        test_db: Session,
        sample_team: Team,
    ):
        """Test checking team quota."""
        # Create some runners
        for i in range(3):
            runner = Runner(
                runner_name=f"runner-{i}",
                team_id=sample_team.id,
                team_name=sample_team.name,
                status="active",
                labels=json.dumps(["test"]),
                provisioned_by="test@example.com",
                runner_group_id=1,
                github_url="https://github.com/test-org",
            )
            test_db.add(runner)
        test_db.commit()

        current_count, max_runners = team_service.check_team_quota(sample_team.id)

        assert current_count == 3
        assert max_runners == 10

    def test_check_team_quota_no_limit(
        self, team_service: TeamService, test_db: Session
    ):
        """Test checking quota for team with no limit."""
        team = team_service.create_team(
            name="unlimited-team",
            required_labels=["test"],
            max_runners=None,
        )

        current_count, max_runners = team_service.check_team_quota(team.id)

        assert current_count == 0
        assert max_runners is None

    def test_is_team_quota_exceeded_false(
        self,
        team_service: TeamService,
        test_db: Session,
        sample_team: Team,
    ):
        """Test quota not exceeded."""
        # Create 5 runners (limit is 10)
        for i in range(5):
            runner = Runner(
                runner_name=f"runner-{i}",
                team_id=sample_team.id,
                team_name=sample_team.name,
                status="active",
                labels=json.dumps(["test"]),
                provisioned_by="test@example.com",
                runner_group_id=1,
                github_url="https://github.com/test-org",
            )
            test_db.add(runner)
        test_db.commit()

        assert not team_service.is_team_quota_exceeded(sample_team.id)

    def test_is_team_quota_exceeded_true(
        self,
        team_service: TeamService,
        test_db: Session,
        sample_team: Team,
    ):
        """Test quota exceeded."""
        # Create 10 runners (limit is 10)
        for i in range(10):
            runner = Runner(
                runner_name=f"runner-{i}",
                team_id=sample_team.id,
                team_name=sample_team.name,
                status="active",
                labels=json.dumps(["test"]),
                provisioned_by="test@example.com",
                runner_group_id=1,
                github_url="https://github.com/test-org",
            )
            test_db.add(runner)
        test_db.commit()

        assert team_service.is_team_quota_exceeded(sample_team.id)

    def test_is_team_quota_exceeded_no_limit(
        self, team_service: TeamService, test_db: Session
    ):
        """Test quota with no limit is never exceeded."""
        team = team_service.create_team(
            name="unlimited-team",
            required_labels=["test"],
            max_runners=None,
        )

        # Create many runners
        for i in range(100):
            runner = Runner(
                runner_name=f"runner-{i}",
                team_id=team.id,
                team_name=team.name,
                status="active",
                labels=json.dumps(["test"]),
                provisioned_by="test@example.com",
                runner_group_id=1,
                github_url="https://github.com/test-org",
            )
            test_db.add(runner)
        test_db.commit()

        assert not team_service.is_team_quota_exceeded(team.id)

    def test_quota_only_counts_active_runners(
        self,
        team_service: TeamService,
        test_db: Session,
        sample_team: Team,
    ):
        """Test that quota only counts pending/active runners."""
        # Create runners with different statuses
        statuses = ["pending", "active", "offline", "removed"]
        for i, status in enumerate(statuses):
            runner = Runner(
                runner_name=f"runner-{i}",
                team_id=sample_team.id,
                team_name=sample_team.name,
                status=status,
                labels=json.dumps(["test"]),
                provisioned_by="test@example.com",
                runner_group_id=1,
                github_url="https://github.com/test-org",
            )
            test_db.add(runner)
        test_db.commit()

        current_count, _ = team_service.check_team_quota(sample_team.id)

        # Should only count pending and active (2 runners)
        assert current_count == 2


# Made with Bob
