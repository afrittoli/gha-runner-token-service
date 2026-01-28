"""Label policy enforcement service."""

import json
import re
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from app.models import LabelPolicy, SecurityEvent


class LabelPolicyViolation(Exception):
    """Raised when label policy is violated."""

    def __init__(self, message: str, invalid_labels: Set[str]):
        super().__init__(message)
        self.invalid_labels = invalid_labels


class LabelPolicyService:
    """Service for enforcing label policies on runner provisioning."""

    def __init__(self, db: Session):
        self.db = db

    def get_policy(self, user_identity: str) -> Optional[LabelPolicy]:
        """
        Retrieve label policy for a user.

        Args:
            user_identity: User identity from OIDC token

        Returns:
            LabelPolicy if exists, None otherwise
        """
        return (
            self.db.query(LabelPolicy)
            .filter(LabelPolicy.user_identity == user_identity)
            .first()
        )

    def validate_labels(self, user_identity: str, requested_labels: List[str]) -> None:
        """
        Validate requested labels against user's policy.

        System labels (self-hosted, OS, architecture) are automatically allowed
        and excluded from policy validation.

        Args:
            user_identity: User identity from OIDC token
            requested_labels: Labels requested for runner

        Raises:
            LabelPolicyViolation: If labels violate policy
            ValueError: If no policy exists for user
        """
        policy = self.get_policy(user_identity)

        if not policy:
            # No policy configured - use default behavior
            # Option 1: Allow all labels (permissive)
            # Option 2: Deny all labels (restrictive) - uncomment below
            # raise ValueError(f"No label policy configured for user: {user_identity}")
            return

        # Parse allowed labels from JSON
        allowed_labels = set(json.loads(policy.allowed_labels))

        # Check for wildcard (allows all labels)
        if "*" in allowed_labels:
            return

        # Parse label patterns if configured
        label_patterns = (
            json.loads(policy.label_patterns) if policy.label_patterns else None
        )

        # Filter out system labels - they are always allowed
        user_labels = [
            label for label in requested_labels if self._is_user_label(label)
        ]

        # Validate each user-defined label
        invalid_labels = set()
        for label in user_labels:
            # Check exact match
            if label in allowed_labels:
                continue

            # Check pattern match
            matched = False
            if label_patterns:
                for pattern in label_patterns:
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
                f"Allowed patterns: {label_patterns}"
                if label_patterns
                else "No patterns configured"
            )
            raise LabelPolicyViolation(
                f"Labels {invalid_labels} not permitted by policy. "
                f"Allowed labels: {allowed_labels}. "
                f"{patterns_msg}",
                invalid_labels=invalid_labels,
            )

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

    def check_runner_quota(self, user_identity: str, current_count: int) -> None:
        """
        Check if user has exceeded runner quota.

        Args:
            user_identity: User identity from OIDC token
            current_count: Current number of active runners

        Raises:
            ValueError: If quota exceeded
        """
        policy = self.get_policy(user_identity)

        if policy and policy.max_runners is not None:
            if current_count >= policy.max_runners:
                raise ValueError(
                    f"Runner quota exceeded. Maximum allowed: {policy.max_runners}, "
                    f"current: {current_count}"
                )

    def verify_labels_match(
        self, expected_labels: List[str], actual_labels: List[str]
    ) -> Set[str]:
        """
        Verify that actual labels match expected labels.

        System labels (self-hosted, OS, architecture) are excluded from comparison.

        Args:
            expected_labels: Labels that should be present
            actual_labels: Labels actually configured on runner

        Returns:
            Set of labels that are missing or don't match
        """
        expected_set = {
            label for label in expected_labels if self._is_user_label(label)
        }
        actual_set = {label for label in actual_labels if self._is_user_label(label)}

        # Check if all expected labels are present
        missing_labels = expected_set - actual_set

        # Check for unexpected labels (potential policy violation)
        unexpected_labels = actual_set - expected_set

        return missing_labels | unexpected_labels

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

        Returns:
            Created SecurityEvent
        """
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            user_identity=user_identity,
            oidc_sub=oidc_sub,
            runner_id=runner_id,
            runner_name=runner_name,
            github_runner_id=github_runner_id,
            violation_data=json.dumps(violation_data),
            action_taken=action_taken,
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        return event

    # Team-based authorization methods

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

    def create_policy(
        self,
        user_identity: str,
        allowed_labels: List[str],
        label_patterns: Optional[List[str]] = None,
        max_runners: Optional[int] = None,
        require_approval: bool = False,
        description: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> LabelPolicy:
        """
        Create or update label policy for a user.

        Args:
            user_identity: User identity to apply policy to
            allowed_labels: List of explicitly allowed labels
            label_patterns: List of regex patterns for allowed labels
            max_runners: Maximum concurrent runners
            require_approval: Whether provisioning requires admin approval
            description: Policy description
            created_by: Admin who created the policy

        Returns:
            Created or updated LabelPolicy
        """
        # Check if policy exists
        existing = self.get_policy(user_identity)

        if existing:
            # Update existing policy
            existing.allowed_labels = json.dumps(allowed_labels)
            existing.label_patterns = (
                json.dumps(label_patterns) if label_patterns else None
            )
            existing.max_runners = max_runners
            existing.require_approval = require_approval
            existing.description = description
            policy = existing
        else:
            # Create new policy
            policy = LabelPolicy(
                user_identity=user_identity,
                allowed_labels=json.dumps(allowed_labels),
                label_patterns=json.dumps(label_patterns) if label_patterns else None,
                max_runners=max_runners,
                require_approval=require_approval,
                description=description,
                created_by=created_by,
            )
            self.db.add(policy)

        self.db.commit()
        self.db.refresh(policy)

        return policy

    def delete_policy(self, user_identity: str) -> bool:
        """
        Delete label policy for a user.

        Args:
            user_identity: User identity

        Returns:
            True if policy was deleted, False if not found
        """
        policy = self.get_policy(user_identity)

        if policy:
            self.db.delete(policy)
            self.db.commit()
            return True

        return False

    def list_policies(self, limit: int = 100, offset: int = 0) -> List[LabelPolicy]:
        """
        List all label policies.

        Args:
            limit: Maximum number of policies to return
            offset: Offset for pagination

        Returns:
            List of LabelPolicy objects
        """
        return (
            self.db.query(LabelPolicy)
            .order_by(LabelPolicy.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
