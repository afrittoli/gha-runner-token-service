"""Team management and authorization service."""

import json
import re
from datetime import datetime, timezone
from typing import List, Optional, Set, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import Runner, Team, User, UserTeamMembership


class TeamPolicyViolation(Exception):
    """Raised when team policy is violated."""

    def __init__(self, message: str, invalid_labels: Optional[Set[str]] = None):
        super().__init__(message)
        self.invalid_labels = invalid_labels or set()


class TeamService:
    """Service for team management and policy enforcement."""

    # System labels that are always allowed and don't need policy validation
    SYSTEM_LABELS = {
        "self-hosted",
        "linux",
        "windows",
        "macos",
        "x64",
        "arm",
        "arm64",
    }

    def __init__(self, db: Session):
        self.db = db

    # Team CRUD operations

    def create_team(
        self,
        name: str,
        required_labels: List[str],
        description: Optional[str] = None,
        optional_label_patterns: Optional[List[str]] = None,
        max_runners: Optional[int] = None,
        created_by: Optional[str] = None,
    ) -> Team:
        """
        Create a new team.

        Args:
            name: Unique team name (kebab-case)
            required_labels: Labels that are always added to runners
            description: Team description
            optional_label_patterns: Regex patterns for optional labels
            max_runners: Maximum concurrent runners for team
            created_by: Admin who created the team

        Returns:
            Created Team object

        Raises:
            ValueError: If team name already exists or is invalid
        """
        # Validate team name format (kebab-case)
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", name):
            raise ValueError(
                "Team name must be kebab-case (lowercase, alphanumeric, hyphens)"
            )

        # Check if team already exists
        existing = self.db.query(Team).filter(Team.name == name).first()
        if existing:
            raise ValueError(f"Team '{name}' already exists")

        team = Team(
            name=name,
            description=description,
            required_labels=json.dumps(required_labels),
            optional_label_patterns=(
                json.dumps(optional_label_patterns) if optional_label_patterns else None
            ),
            max_runners=max_runners,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by=created_by,
        )

        self.db.add(team)
        self.db.commit()
        self.db.refresh(team)

        return team

    def get_team(self, team_id: str) -> Optional[Team]:
        """Get team by ID."""
        return self.db.query(Team).filter(Team.id == team_id).first()

    def get_team_by_name(self, name: str) -> Optional[Team]:
        """Get team by name."""
        return self.db.query(Team).filter(Team.name == name).first()

    def list_teams(
        self, include_inactive: bool = False, limit: int = 100, offset: int = 0
    ) -> List[Team]:
        """
        List teams.

        Args:
            include_inactive: Include deactivated teams
            limit: Maximum number of teams to return
            offset: Number of teams to skip

        Returns:
            List of Team objects
        """
        query = self.db.query(Team)

        if not include_inactive:
            query = query.filter(Team.is_active == True)  # noqa: E712

        return query.order_by(Team.name).limit(limit).offset(offset).all()

    def update_team(
        self,
        team_id: str,
        description: Optional[str] = None,
        required_labels: Optional[List[str]] = None,
        optional_label_patterns: Optional[List[str]] = None,
        max_runners: Optional[int] = None,
    ) -> Team:
        """
        Update team configuration.

        Args:
            team_id: Team ID
            description: New description
            required_labels: New required labels
            optional_label_patterns: New optional label patterns
            max_runners: New max runners limit

        Returns:
            Updated Team object

        Raises:
            ValueError: If team not found
        """
        team = self.get_team(team_id)
        if not team:
            raise ValueError(f"Team not found: {team_id}")

        if description is not None:
            team.description = description
        if required_labels is not None:
            team.required_labels = json.dumps(required_labels)
        if optional_label_patterns is not None:
            team.optional_label_patterns = json.dumps(optional_label_patterns)
        if max_runners is not None:
            team.max_runners = max_runners

        team.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(team)

        return team

    def deactivate_team(
        self,
        team_id: str,
        reason: str,
        deactivated_by: str,
    ) -> Team:
        """
        Deactivate a team.

        Args:
            team_id: Team ID
            reason: Reason for deactivation
            deactivated_by: Admin who deactivated the team

        Returns:
            Deactivated Team object

        Raises:
            ValueError: If team not found or already deactivated
        """
        team = self.get_team(team_id)
        if not team:
            raise ValueError(f"Team not found: {team_id}")

        if not team.is_active:
            raise ValueError(f"Team '{team.name}' is already deactivated")

        team.is_active = False
        team.deactivation_reason = reason
        team.deactivated_at = datetime.now(timezone.utc)
        team.deactivated_by = deactivated_by
        team.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(team)

        return team

    def reactivate_team(self, team_id: str) -> Team:
        """
        Reactivate a deactivated team.

        Args:
            team_id: Team ID

        Returns:
            Reactivated Team object

        Raises:
            ValueError: If team not found or already active
        """
        team = self.get_team(team_id)
        if not team:
            raise ValueError(f"Team not found: {team_id}")

        if team.is_active:
            raise ValueError(f"Team '{team.name}' is already active")

        team.is_active = True
        team.deactivation_reason = None
        team.deactivated_at = None
        team.deactivated_by = None
        team.updated_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(team)

        return team

    # Team membership operations

    def add_user_to_team(
        self,
        user_id: str,
        team_id: str,
        added_by: Optional[str] = None,
    ) -> UserTeamMembership:
        """
        Add a user to a team.

        Args:
            user_id: User ID
            team_id: Team ID
            added_by: Admin who added the user

        Returns:
            Created UserTeamMembership object

        Raises:
            ValueError: If user/team not found or membership exists
        """
        # Verify user exists
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Verify team exists
        team = self.get_team(team_id)
        if not team:
            raise ValueError(f"Team not found: {team_id}")

        # Check if membership already exists
        existing = (
            self.db.query(UserTeamMembership)
            .filter(
                and_(
                    UserTeamMembership.user_id == user_id,
                    UserTeamMembership.team_id == team_id,
                )
            )
            .first()
        )
        if existing:
            raise ValueError(
                f"User {user.email} is already a member of team {team.name}"
            )

        membership = UserTeamMembership(
            user_id=user_id,
            team_id=team_id,
            joined_at=datetime.now(timezone.utc),
            added_by=added_by,
        )

        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)

        return membership

    def remove_user_from_team(self, user_id: str, team_id: str) -> None:
        """
        Remove a user from a team.

        Args:
            user_id: User ID
            team_id: Team ID

        Raises:
            ValueError: If membership not found
        """
        membership = (
            self.db.query(UserTeamMembership)
            .filter(
                and_(
                    UserTeamMembership.user_id == user_id,
                    UserTeamMembership.team_id == team_id,
                )
            )
            .first()
        )

        if not membership:
            raise ValueError("User is not a member of this team")

        self.db.delete(membership)
        self.db.commit()

    def get_user_teams(self, user_id: str) -> List[Team]:
        """
        Get all teams a user belongs to.

        Args:
            user_id: User ID

        Returns:
            List of Team objects
        """
        memberships = (
            self.db.query(UserTeamMembership)
            .filter(UserTeamMembership.user_id == user_id)
            .all()
        )

        team_ids = [m.team_id for m in memberships]
        if not team_ids:
            return []

        return (
            self.db.query(Team).filter(Team.id.in_(team_ids)).order_by(Team.name).all()
        )

    def get_team_members(self, team_id: str) -> List[User]:
        """
        Get all users in a team.

        Args:
            team_id: Team ID

        Returns:
            List of User objects
        """
        memberships = (
            self.db.query(UserTeamMembership)
            .filter(UserTeamMembership.team_id == team_id)
            .all()
        )

        user_ids = [m.user_id for m in memberships]
        if not user_ids:
            return []

        return (
            self.db.query(User).filter(User.id.in_(user_ids)).order_by(User.email).all()
        )

    def is_user_in_team(self, user_id: str, team_id: str) -> bool:
        """Check if a user is a member of a team."""
        membership = (
            self.db.query(UserTeamMembership)
            .filter(
                and_(
                    UserTeamMembership.user_id == user_id,
                    UserTeamMembership.team_id == team_id,
                )
            )
            .first()
        )
        return membership is not None

    # Label policy enforcement

    def validate_and_merge_labels(
        self,
        team_id: str,
        optional_labels: List[str],
    ) -> Tuple[List[str], Set[str]]:
        """
        Validate optional labels and merge with team's required labels.

        Args:
            team_id: Team ID
            optional_labels: Optional labels requested by user

        Returns:
            Tuple of (merged_labels, invalid_labels)
            - merged_labels: Required + valid optional labels
            - invalid_labels: Optional labels that don't match patterns

        Raises:
            ValueError: If team not found or inactive
            TeamPolicyViolation: If optional labels violate policy
        """
        team = self.get_team(team_id)
        if not team:
            raise ValueError(f"Team not found: {team_id}")

        if not team.is_active:
            raise ValueError(f"Team '{team.name}' is deactivated")

        # Parse required labels
        required_labels = json.loads(team.required_labels)

        # If no optional labels requested, return required labels only
        if not optional_labels:
            return required_labels, set()

        # Parse optional label patterns
        patterns = (
            json.loads(team.optional_label_patterns)
            if team.optional_label_patterns
            else []
        )

        # Filter out system labels from validation
        user_optional_labels = [
            label for label in optional_labels if label not in self.SYSTEM_LABELS
        ]

        # Validate optional labels against patterns
        invalid_labels = set()
        valid_optional_labels = []

        for label in user_optional_labels:
            # Check if label matches any pattern
            matched = False
            for pattern in patterns:
                try:
                    if re.match(pattern, label):
                        matched = True
                        valid_optional_labels.append(label)
                        break
                except re.error:
                    # Invalid regex pattern - skip
                    continue

            if not matched:
                invalid_labels.add(label)

        # If there are invalid labels, raise violation
        if invalid_labels:
            raise TeamPolicyViolation(
                f"Labels do not match team '{team.name}' patterns: "
                f"{', '.join(sorted(invalid_labels))}",
                invalid_labels=invalid_labels,
            )

        # Merge required + valid optional labels (deduplicate)
        merged_labels = list(set(required_labels + valid_optional_labels))

        return merged_labels, invalid_labels

    def check_team_quota(self, team_id: str) -> Tuple[int, Optional[int]]:
        """
        Check team's current runner count against quota.

        Args:
            team_id: Team ID

        Returns:
            Tuple of (current_count, max_runners)

        Raises:
            ValueError: If team not found
        """
        team = self.get_team(team_id)
        if not team:
            raise ValueError(f"Team not found: {team_id}")

        # Count active runners for this team
        current_count = (
            self.db.query(Runner)
            .filter(
                and_(
                    Runner.team_id == team_id,
                    Runner.status.in_(["pending", "active"]),
                )
            )
            .count()
        )

        return current_count, team.max_runners

    def is_team_quota_exceeded(self, team_id: str) -> bool:
        """
        Check if team has exceeded its runner quota.

        Args:
            team_id: Team ID

        Returns:
            True if quota is exceeded, False otherwise
        """
        current_count, max_runners = self.check_team_quota(team_id)

        # No quota set means unlimited
        if max_runners is None:
            return False

        return current_count >= max_runners


# Made with Bob
