"""Runner provisioning and management service."""

import json
import secrets
import structlog
from datetime import datetime, timedelta
from typing import List, Optional

import httpx
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.config import Settings
from app.github.client import GitHubClient
from app.models import AuditLog, Runner, Team
from app.schemas import (
    JitProvisionRequest,
    JitProvisionResponse,
)
from app.services.label_policy_service import LabelPolicyService, LabelPolicyViolation

logger = structlog.get_logger()

SYSTEM_LABELS = ["self-hosted"]


class RunnerService:
    """Service for runner provisioning and management."""

    def __init__(self, settings: Settings, db: Session):
        self.settings = settings
        self.db = db
        self.github = GitHubClient(settings)

    def _generate_unique_runner_name(self, prefix: str) -> str:
        """
        Generate a unique runner name from a prefix.

        Args:
            prefix: Runner name prefix

        Returns:
            Unique runner name in format 'prefix-xxxxxx'
        """
        suffix = secrets.token_hex(3)  # 6 character hex string
        return f"{prefix}-{suffix}"

    def _is_runner_name_active(self, runner_name: str) -> bool:
        """
        Check if a runner name is currently active (not deleted).

        Args:
            runner_name: Runner name to check

        Returns:
            True if runner with this name exists and is not deleted
        """
        existing = (
            self.db.query(Runner)
            .filter(Runner.runner_name == runner_name, Runner.status != "deleted")
            .first()
        )
        return existing is not None

    async def provision_runner_jit(
        self, request: JitProvisionRequest, user: AuthenticatedUser
    ) -> JitProvisionResponse:
        """
        Provision a runner using JIT configuration.

        JIT provisioning offers stronger security guarantees:
        - Labels are enforced server-side and cannot be overridden
        - Ephemeral mode is always enabled
        - No separate config step needed (direct run.sh)

        Args:
            request: JIT provisioning request
            user: Authenticated user

        Returns:
            JIT provisioning response with encoded config

        Raises:
            ValueError: If runner name already active or quota exceeded
            LabelPolicyViolation: If labels violate policy
        """
        provision_label = list(set(request.labels + SYSTEM_LABELS))
        # Determine runner name
        if request.runner_name_prefix:
            runner_name = self._generate_unique_runner_name(request.runner_name_prefix)
            max_attempts = 5
            for _ in range(max_attempts):
                if not self._is_runner_name_active(runner_name):
                    break
                runner_name = self._generate_unique_runner_name(
                    request.runner_name_prefix
                )
            else:
                raise ValueError(
                    f"Failed to generate unique name for prefix "
                    f"'{request.runner_name_prefix}' after {max_attempts} attempts"
                )
        else:
            runner_name = request.runner_name
            if self._is_runner_name_active(runner_name):
                raise ValueError(
                    f"Runner with name '{runner_name}' is currently active. "
                    f"Use a different name or wait until it's deleted."
                )

        # Initialize label policy service
        label_policy_service = LabelPolicyService(self.db)

        # Get team ID for provisioning (team-based authorization)
        try:
            if user.team is not None:
                # M2M token: team is resolved directly from JWT claim, no membership lookup
                team_id = user.team.id
            else:
                team_id = label_policy_service.get_user_team_for_provisioning(
                    user_id=user.db_user.id if user.db_user else None,
                    team_id=request.team_id,
                )
        except ValueError as e:
            self._log_audit(
                event_type="provision_jit_failed",
                runner_name=runner_name,
                user=user,
                success=False,
                error_message=str(e),
            )
            raise

        # Validate labels against team policy
        try:
            label_policy_service.validate_labels_for_team(team_id, request.labels)
        except LabelPolicyViolation as e:
            label_policy_service.log_security_event(
                event_type="label_policy_violation",
                severity="medium",
                user_id=user.identity,
                runner_id=None,
                runner_name=runner_name,
                team_id=team_id,
                violation_data={
                    "requested_labels": request.labels,
                    "invalid_labels": list(e.invalid_labels),
                    "provisioning_method": "jit",
                    "team_id": team_id,
                },
                action_taken="rejected",
            )

            self._log_audit(
                event_type="provision_jit_failed",
                runner_name=runner_name,
                team_id=team_id,
                user=user,
                success=False,
                error_message=str(e),
            )
            raise

        # Check team runner quota
        active_runner_count = (
            self.db.query(Runner)
            .filter(
                Runner.team_id == team_id,
                Runner.status.in_(["pending", "active", "offline"]),
            )
            .count()
        )

        try:
            label_policy_service.check_team_quota(team_id, active_runner_count)
        except ValueError as e:
            label_policy_service.log_security_event(
                event_type="quota_exceeded",
                severity="low",
                user_id=user.identity,
                runner_id=None,
                runner_name=runner_name,
                team_id=team_id,
                violation_data={
                    "current_count": active_runner_count,
                    "provisioning_method": "jit",
                    "team_id": team_id,
                },
                action_taken="rejected",
            )

            self._log_audit(
                event_type="provision_jit_failed",
                runner_name=runner_name,
                team_id=team_id,
                user=user,
                success=False,
                error_message=str(e),
            )
            raise

        # Get team name for denormalization
        team = self.db.query(Team).filter(Team.id == team_id).first()
        if not team:
            raise ValueError(f"Team {team_id} not found")

        team_name = team.name

        # Determine runner group
        runner_group_id = (
            request.runner_group_id or self.settings.default_runner_group_id
        )

        # Generate JIT config from GitHub
        try:
            jit_response = await self.github.generate_jit_config(
                name=runner_name,
                runner_group_id=runner_group_id,
                labels=provision_label,
                work_folder=request.work_folder,
            )
        except httpx.HTTPStatusError as e:
            error_detail = str(e)
            # Try to get more details from the response
            try:
                error_data = e.response.json()
                error_detail = error_data.get("message", str(e))
            except Exception:
                pass
            self._log_audit(
                event_type="provision_jit_failed",
                runner_name=runner_name,
                team_id=team_id,
                user=user,
                success=False,
                error_message=f"GitHub API error: {error_detail}",
                event_data=request.model_dump(),
            )
            raise ValueError(f"GitHub API error: {error_detail}")
        except Exception as e:
            self._log_audit(
                event_type="provision_jit_failed",
                runner_name=runner_name,
                team_id=team_id,
                user=user,
                success=False,
                error_message=f"Failed to generate JIT config: {str(e)}",
                event_data=request.model_dump(),
            )
            raise

        # Create runner record
        # Note: JIT runners are always ephemeral
        runner = Runner(
            runner_name=runner_name,
            runner_group_id=runner_group_id,
            labels=json.dumps(provision_label),
            ephemeral=True,  # JIT enforces ephemeral
            disable_update=False,
            provisioned_by=user.identity,
            team_id=team_id,
            team_name=team_name,
            status="pending",
            github_runner_id=jit_response.runner_id,  # Set immediately
            github_url=f"https://github.com/{self.settings.github_org}",
        )

        self.db.add(runner)
        self.db.commit()
        self.db.refresh(runner)

        # Log audit event
        self._log_audit(
            event_type="provision_jit",
            runner_id=runner.id,
            runner_name=runner.runner_name,
            team_id=team_id,
            user=user,
            success=True,
            event_data={
                "runner_group_id": runner_group_id,
                "labels": provision_label,
                "github_runner_id": jit_response.runner_id,
                "provisioning_method": "jit",
                "team_id": team_id,
                "team_name": team_name,
            },
        )

        # Build run command
        run_cmd = f"./run.sh --jitconfig {jit_response.encoded_jit_config}"

        # JIT config expires in 1 hour (GitHub's default)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        return JitProvisionResponse(
            runner_id=runner.id,
            runner_name=runner.runner_name,
            encoded_jit_config=jit_response.encoded_jit_config,
            labels=provision_label,
            expires_at=expires_at,
            run_command=run_cmd,
        )

    async def get_runner_by_id(
        self, runner_id: str, user: AuthenticatedUser
    ) -> Optional[Runner]:
        """
        Get runner by ID.

        For standard users, only returns if owned.
        For admins, returns any runner.

        Args:
            runner_id: Runner UUID
            user: Authenticated user

        Returns:
            Runner if found and authorized, None otherwise
        """

        query = self.db.query(Runner).filter(Runner.id == runner_id)

        # If not admin, enforce ownership
        if not user.is_admin:
            query = query.filter(Runner.provisioned_by == user.identity)

        return query.first()

    async def get_runner_by_name(
        self, runner_name: str, user: AuthenticatedUser
    ) -> Optional[Runner]:
        """
        Get runner by name.

        For standard users, only returns if owned.
        For admins, returns any runner.

        Note: If multiple runners with the same name exist, returns the most recent non-deleted one.

        Args:
            runner_name: Runner name
            user: Authenticated user

        Returns:
            Runner if found and authorized, None otherwise
        """

        query = self.db.query(Runner).filter(
            Runner.runner_name == runner_name,
            Runner.status != "deleted",
        )

        # If not admin, enforce ownership
        if not user.is_admin:
            query = query.filter(Runner.provisioned_by == user.identity)

        return query.order_by(Runner.created_at.desc()).first()

    async def list_runners(
        self,
        user: AuthenticatedUser,
        team_name: Optional[str] = None,
    ) -> List[Runner]:
        """List runners with team-scoped visibility.

        Visibility rules:
        - **Admin**: all runners (optionally filtered by ``team_name``).
        - **M2M team token**: only runners belonging to the token's team.
        - **Individual user**: runners provisioned by the user *or* any runner
          belonging to a team the user is a member of.  Optionally filtered by
          ``team_name`` (must be one of the user's teams).

        Args:
            user: Authenticated user.
            team_name: Optional team name to filter results.

        Returns:
            List of non-deleted runners matching the visibility rules.
        """
        from sqlalchemy import or_

        from app.auth.token_types import TokenType
        from app.models import UserTeamMembership

        query = self.db.query(Runner).filter(Runner.status != "deleted")

        if user.is_admin:
            # Admins see everything; optional team filter
            if team_name:
                query = query.filter(Runner.team_name == team_name)

        elif user.token_type == TokenType.M2M_TEAM:
            # M2M: restricted to the credential's own team
            query = query.filter(Runner.team_id == user.team.id)

        else:
            # Individual user: own runners + all runners for their teams
            memberships = (
                self.db.query(UserTeamMembership.team_id)
                .filter(UserTeamMembership.user_id == user.user_id)
                .scalar_subquery()
            )
            query = query.filter(
                or_(
                    Runner.provisioned_by == user.identity,
                    Runner.team_id.in_(memberships),
                )
            )
            if team_name:
                query = query.filter(Runner.team_name == team_name)

        return query.order_by(Runner.created_at.desc()).all()

    async def update_runner_status(
        self, runner_id: str, user: AuthenticatedUser
    ) -> Optional[Runner]:
        """
        Update runner status from GitHub API.

        Args:
            runner_id: Runner UUID
            user: Authenticated user

        Returns:
            Updated runner or None if not found
        """
        runner = await self.get_runner_by_id(runner_id, user)
        if not runner:
            return None

        # Fetch status from GitHub
        try:
            github_runner = await self.github.get_runner_by_name(runner.runner_name)
            logger.debug(
                "fetched_github_runner",
                runner_id=runner.id,
                github_runner_id=github_runner.id if github_runner else None,
                status=github_runner.status if github_runner else None,
            )

            if github_runner:
                # Runner exists in GitHub
                runner.github_runner_id = github_runner.id
                runner.status = github_runner.status  # online or offline

                if runner.registered_at is None:
                    runner.registered_at = datetime.utcnow()

            else:
                # Runner not found in GitHub
                if runner.status == "pending":
                    # Still pending registration
                    pass
                else:
                    # Was registered but now deleted (ephemeral or manual deletion)
                    runner.status = "deleted"
                    runner.deleted_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(runner)

        except Exception as e:
            # Log error but don't fail
            self._log_audit(
                event_type="update_status_failed",
                runner_id=runner.id,
                runner_name=runner.runner_name,
                team_id=runner.team_id,
                user=user,
                success=False,
                error_message=str(e),
            )

        return runner

    async def deprovision_runner(self, runner_id: str, user: AuthenticatedUser) -> bool:
        """
        Deprovision a runner.

        Args:
            runner_id: Runner UUID
            user: Authenticated user

        Returns:
            True if successfully deprovisioned

        Raises:
            ValueError: If runner not found or not owned by user
        """
        runner = await self.get_runner_by_id(runner_id, user)
        if not runner:
            raise ValueError(
                f"Runner with ID '{runner_id}' not found or not owned by you"
            )

        if runner.status == "deleted":
            raise ValueError(f"Runner '{runner.runner_name}' is already deleted")

        # Delete from GitHub if it has a GitHub ID
        if runner.github_runner_id:
            try:
                deleted = await self.github.delete_runner(runner.github_runner_id)
                if not deleted:
                    # Runner not found in GitHub (already deleted)
                    pass
            except Exception as e:
                self._log_audit(
                    event_type="deprovision_failed",
                    runner_id=runner.id,
                    runner_name=runner.runner_name,
                    team_id=runner.team_id,
                    user=user,
                    success=False,
                    error_message=f"Failed to delete from GitHub: {str(e)}",
                )
                raise

        # Update local state
        runner.status = "deleted"
        runner.deleted_at = datetime.utcnow()

        self.db.commit()

        # Log audit event
        self._log_audit(
            event_type="deprovision",
            runner_id=runner.id,
            runner_name=runner.runner_name,
            team_id=runner.team_id,
            user=user,
            success=True,
        )

        return True

    def _log_audit(
        self,
        event_type: str,
        user: AuthenticatedUser,
        success: bool,
        runner_id: Optional[str] = None,
        runner_name: Optional[str] = None,
        team_id: Optional[str] = None,
        error_message: Optional[str] = None,
        event_data: Optional[dict] = None,
    ):
        """Log an audit event."""
        # If team_id was not provided explicitly, try to look it up from the runner
        resolved_team_id = team_id
        if resolved_team_id is None and runner_id is not None:
            runner_row = self.db.query(Runner).filter(Runner.id == runner_id).first()
            if runner_row is not None:
                resolved_team_id = runner_row.team_id

        audit = AuditLog(
            event_type=event_type,
            runner_id=runner_id,
            runner_name=runner_name,
            team_id=resolved_team_id,
            user_id=user.identity,
            success=success,
            error_message=error_message,
            event_data=json.dumps(event_data) if event_data else None,
        )

        self.db.add(audit)
        self.db.commit()
