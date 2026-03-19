"""Label policy enforcement service."""

import json
import re
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from app.models import SecurityEvent


class LabelPolicyViolation(Exception):
    """Raised when label policy is violated."""

    def __init__(self, message: str, invalid_labels: Set[str]):
        super().__init__(message)
        self.invalid_labels = invalid_labels


class LabelPolicyService:
    """Service for enforcing team-based label policies on runner provisioning."""

    def __init__(self, db: Session):
        self.db = db

    # System labels that are automatically added by GitHub and should be
    # excluded from policy validation
    SYSTEM_LABEL_PREFIXES = [
        "self-hosted",
    ]

    def _is_user_label(self, label: str) -> bool:
        """
        Check if label is user-defined (not system-generated).

        Args:
            label: Label to check

        Returns:
            True if this is a user-defined label, False if system label
        """
        label_lower = label.lower()
        return not any(
            label_lower.startswith(prefix) for prefix in self.SYSTEM_LABEL_PREFIXES
        )

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        user_identity: str,
        runner_id: Optional[str],
        runner_name: Optional[str],
        violation_data: dict,
        action_taken: Optional[str] = None,
        oidc_sub: Optional[str] = None,
        github_runner_id: Optional[int] = None,
        team_id: Optional[str] = None,
    ) -> SecurityEvent:
        """
        Log a security event for monitoring and alerting.

        Args:
            event_type: Type of security event
            severity: Event severity (low, medium, high, critical)
            user_identity: User who triggered the event
            runner_id: Internal runner ID
            runner_name: Runner name
            violation_data: Details of the violation
            action_taken: Action taken in response
            oidc_sub: OIDC subject claim
            github_runner_id: GitHub runner ID
            team_id: Team this event is scoped to (nullable)

        Returns:
            Created SecurityEvent
        """
        # If team_id not supplied, try to resolve it from the runner record
        resolved_team_id = team_id
        if resolved_team_id is None and runner_id is not None:
            from app.models import Runner as RunnerModel

            runner_row = (
                self.db.query(RunnerModel).filter(RunnerModel.id == runner_id).first()
            )
            if runner_row is not None:
                resolved_team_id = runner_row.team_id

        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            user_identity=user_identity,
            oidc_sub=oidc_sub,
            runner_id=runner_id,
            runner_name=runner_name,
            github_runner_id=github_runner_id,
            team_id=resolved_team_id,
            violation_data=json.dumps(violation_data),
            action_taken=action_taken,
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        return event

    def validate_labels_for_team(
        self, team_id: str, requested_labels: List[str]
    ) -> None:
        """
        Validate requested labels against team's policy.

        System labels (self-hosted, OS, architecture) are automatically allowed
        and excluded from policy validation.

        Args:
            team_id: Team ID
            requested_labels: Labels requested for runner

        Raises:
            LabelPolicyViolation: If labels violate team policy
            ValueError: If team not found or not active
        """
        from app.models import Team

        team = self.db.query(Team).filter(Team.id == team_id).first()

        if not team:
            raise ValueError(f"Team not found: {team_id}")

        if not team.is_active:
            raise ValueError(f"Team '{team.name}' is not active")

        # Parse required labels from JSON
        required_labels = set(json.loads(team.required_labels))

        # Parse optional label patterns if configured
        optional_patterns = (
            json.loads(team.optional_label_patterns)
            if team.optional_label_patterns
            else []
        )

        # Filter out system labels - they are always allowed
        user_labels = [
            label for label in requested_labels if self._is_user_label(label)
        ]

        # Check that all required labels are present
        missing_required = required_labels - set(user_labels)
        if missing_required:
            raise LabelPolicyViolation(
                f"Missing required labels for team '{team.name}': {missing_required}",
                invalid_labels=missing_required,
            )

        # Validate each user-defined label against allowed patterns
        invalid_labels = set()
        for label in user_labels:
            # Required labels are always valid
            if label in required_labels:
                continue

            # Check optional pattern match
            matched = False
            if optional_patterns:
                for pattern in optional_patterns:
                    try:
                        if re.match(pattern, label):
                            matched = True
                            break
                    except re.error:
                        # Invalid regex pattern - log and skip
                        continue

            if not matched:
                invalid_labels.add(label)

        if invalid_labels:
            patterns_msg = (
                f"Allowed patterns: {optional_patterns}"
                if optional_patterns
                else "No optional patterns configured"
            )
            raise LabelPolicyViolation(
                f"Labels {invalid_labels} not permitted by team '{team.name}' policy. "
                f"Required labels: {required_labels}. "
                f"{patterns_msg}",
                invalid_labels=invalid_labels,
            )

    def check_team_quota(self, team_id: str, current_count: int) -> None:
        """
        Check if team has exceeded runner quota.

        Args:
            team_id: Team ID
            current_count: Current number of active runners for the team

        Raises:
            ValueError: If quota exceeded or team not found
        """
        from app.models import Team

        team = self.db.query(Team).filter(Team.id == team_id).first()

        if not team:
            raise ValueError(f"Team not found: {team_id}")

        if team.max_runners is not None:
            if current_count >= team.max_runners:
                raise ValueError(
                    f"Team '{team.name}' runner quota exceeded. "
                    f"Maximum allowed: {team.max_runners}, current: {current_count}"
                )

    def get_user_team_for_provisioning(
        self, user_id: str, team_id: Optional[str] = None
    ) -> str:
        """
        Get the team ID to use for provisioning.

        If team_id is provided, validates that user is a member.
        If not provided, returns the first active team the user belongs to.

        Args:
            user_id: User ID
            team_id: Optional team ID to use

        Returns:
            Team ID to use for provisioning

        Raises:
            ValueError: If user not in team or has no teams
        """
        from app.models import Team, UserTeamMembership

        if team_id:
            # Validate user is member of specified team
            membership = (
                self.db.query(UserTeamMembership)
                .join(Team)
                .filter(
                    UserTeamMembership.user_id == user_id,
                    UserTeamMembership.team_id == team_id,
                    Team.is_active == True,  # noqa: E712
                )
                .first()
            )

            if not membership:
                raise ValueError(
                    f"User is not a member of team {team_id} or team is not active"
                )

            return team_id
        else:
            # Get first active team user belongs to
            membership = (
                self.db.query(UserTeamMembership)
                .join(Team)
                .filter(
                    UserTeamMembership.user_id == user_id,
                    Team.is_active == True,  # noqa: E712
                )
                .first()
            )

            if not membership:
                raise ValueError(
                    "User is not a member of any active team. "
                    "Please contact an administrator to be added to a team."
                )

            return membership.team_id
