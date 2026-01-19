"""Runner provisioning and management service."""

import asyncio
import json
import secrets
import structlog
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.config import Settings
from app.github.client import GitHubClient
from app.models import AuditLog, Runner
from app.schemas import ProvisionRunnerRequest, ProvisionRunnerResponse
from app.services.label_policy_service import LabelPolicyService, LabelPolicyViolation

logger = structlog.get_logger()


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
        existing = self.db.query(Runner).filter(
            Runner.runner_name == runner_name,
            Runner.status != "deleted"
        ).first()
        return existing is not None

    async def provision_runner(
        self,
        request: ProvisionRunnerRequest,
        user: AuthenticatedUser
    ) -> ProvisionRunnerResponse:
        """
        Provision a new runner with label policy enforcement.

        Args:
            request: Provisioning request
            user: Authenticated user

        Returns:
            Provisioning response with registration token

        Raises:
            ValueError: If runner name already active or quota exceeded
            LabelPolicyViolation: If labels violate policy
        """
        # Determine runner name
        if request.runner_name_prefix:
            # Generate unique name from prefix
            runner_name = self._generate_unique_runner_name(request.runner_name_prefix)
            # Ensure uniqueness (very unlikely to collide, but check anyway)
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
            # Check if runner name is currently active
            if self._is_runner_name_active(runner_name):
                raise ValueError(
                    f"Runner with name '{runner_name}' is currently active. "
                    f"Use a different name or wait until it's deleted."
                )

        # Initialize label policy service
        label_policy_service = LabelPolicyService(self.db)

        # Validate labels against policy (Phase 1: Prevention)
        try:
            label_policy_service.validate_labels(user.identity, request.labels)
        except LabelPolicyViolation as e:
            # Log security event
            label_policy_service.log_security_event(
                event_type="label_policy_violation",
                severity="medium",
                user_identity=user.identity,
                oidc_sub=user.sub,
                runner_id=None,
                runner_name=runner_name,
                violation_data={
                    "requested_labels": request.labels,
                    "invalid_labels": list(e.invalid_labels)
                },
                action_taken="rejected"
            )

            self._log_audit(
                event_type="provision_failed",
                runner_name=runner_name,
                user=user,
                success=False,
                error_message=str(e)
            )
            raise

        # Check runner quota
        active_runner_count = self.db.query(Runner).filter(
            Runner.provisioned_by == user.identity,
            Runner.status.in_(["pending", "active", "offline"])
        ).count()

        try:
            label_policy_service.check_runner_quota(
                user.identity,
                active_runner_count
            )
        except ValueError as e:
            # Log security event
            label_policy_service.log_security_event(
                event_type="quota_exceeded",
                severity="low",
                user_identity=user.identity,
                oidc_sub=user.sub,
                runner_id=None,
                runner_name=runner_name,
                violation_data={
                    "current_count": active_runner_count
                },
                action_taken="rejected"
            )

            self._log_audit(
                event_type="provision_failed",
                runner_name=runner_name,
                user=user,
                success=False,
                error_message=str(e)
            )
            raise

        # Generate registration token from GitHub
        try:
            token, expires_at = await self.github.generate_registration_token()
        except Exception as e:
            self._log_audit(
                event_type="provision_failed",
                runner_name=runner_name,
                user=user,
                success=False,
                error_message=f"Failed to generate GitHub token: {str(e)}",
                event_data=request.model_dump()
            )
            raise

        # Determine runner group
        runner_group_id = (
            request.runner_group_id or self.settings.default_runner_group_id
        )

        # Create runner record
        runner = Runner(
            runner_name=runner_name,
            runner_group_id=runner_group_id,
            labels=json.dumps(request.labels),
            ephemeral=request.ephemeral,
            disable_update=request.disable_update,
            provisioned_by=user.identity,
            oidc_sub=user.sub,
            status="pending",
            registration_token=token,  # Store temporarily
            registration_token_expires_at=expires_at,
            github_url=f"https://github.com/{self.settings.github_org}"
        )

        self.db.add(runner)
        self.db.commit()
        self.db.refresh(runner)

        # Log audit event
        self._log_audit(
            event_type="provision",
            runner_id=runner.id,
            runner_name=runner.runner_name,
            user=user,
            success=True,
            event_data={
                "runner_group_id": runner_group_id,
                "labels": request.labels,
                "ephemeral": request.ephemeral
            }
        )

        # Schedule post-registration verification (Phase 2: Detection)
        asyncio.create_task(
            self._verify_labels_after_registration(
                runner_id=runner.id,
                expected_labels=request.labels,
                user_identity=user.identity,
                oidc_sub=user.sub,
                delay=60
            )
        )

        # Build configuration command
        labels_str = ",".join(request.labels)
        config_cmd = (
            f"./config.sh "
            f"--url {runner.github_url} "
            f"--token {token} "
            f"--name {runner.runner_name} "
            f"--unattended"
        )
        if labels_str:
            config_cmd += f" --labels {labels_str}"
        if request.ephemeral:
            config_cmd += " --ephemeral"
        if request.disable_update:
            config_cmd += " --disableupdate"

        return ProvisionRunnerResponse(
            runner_id=runner.id,
            runner_name=runner.runner_name,
            registration_token=token,
            expires_at=expires_at,
            github_url=runner.github_url,
            runner_group_id=runner_group_id,
            ephemeral=request.ephemeral,
            labels=request.labels,
            configuration_command=config_cmd
        )

    async def get_runner(self, runner_name: str, user: AuthenticatedUser) -> Optional[Runner]:
        """
        Get runner by name (only if owned by user).

        Args:
            runner_name: Runner name
            user: Authenticated user

        Returns:
            Runner if found and owned by user, None otherwise
        """
        runner = self.db.query(Runner).filter(
            Runner.runner_name == runner_name,
            Runner.provisioned_by == user.identity
        ).first()

        return runner

    async def list_runners(self, user: AuthenticatedUser) -> List[Runner]:
        """
        List all runners provisioned by user.

        Args:
            user: Authenticated user

        Returns:
            List of runners
        """
        runners = self.db.query(Runner).filter(
            Runner.provisioned_by == user.identity,
            Runner.status != "deleted"
        ).order_by(Runner.created_at.desc()).all()

        return runners

    async def update_runner_status(
        self,
        runner_name: str,
        user: AuthenticatedUser
    ) -> Optional[Runner]:
        """
        Update runner status from GitHub API.

        Args:
            runner_name: Runner name
            user: Authenticated user

        Returns:
            Updated runner or None if not found
        """
        runner = await self.get_runner(runner_name, user)
        if not runner:
            return None

        # Fetch status from GitHub
        try:
            github_runner = await self.github.get_runner_by_name(runner_name)

            if github_runner:
                # Runner exists in GitHub
                runner.github_runner_id = github_runner.id
                runner.status = github_runner.status  # online or offline

                if runner.registered_at is None:
                    runner.registered_at = datetime.utcnow()

                # Clear registration token after successful registration
                if runner.registration_token:
                    runner.registration_token = None
                    runner.registration_token_expires_at = None
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
                user=user,
                success=False,
                error_message=str(e)
            )

        return runner

    async def deprovision_runner(
        self,
        runner_name: str,
        user: AuthenticatedUser
    ) -> bool:
        """
        Deprovision a runner.

        Args:
            runner_name: Runner name
            user: Authenticated user

        Returns:
            True if successfully deprovisioned

        Raises:
            ValueError: If runner not found or not owned by user
        """
        runner = await self.get_runner(runner_name, user)
        if not runner:
            raise ValueError(f"Runner '{runner_name}' not found or not owned by you")

        if runner.status == "deleted":
            raise ValueError(f"Runner '{runner_name}' is already deleted")

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
                    user=user,
                    success=False,
                    error_message=f"Failed to delete from GitHub: {str(e)}"
                )
                raise

        # Update local state
        runner.status = "deleted"
        runner.deleted_at = datetime.utcnow()

        # Clear sensitive data
        runner.registration_token = None
        runner.registration_token_expires_at = None

        self.db.commit()

        # Log audit event
        self._log_audit(
            event_type="deprovision",
            runner_id=runner.id,
            runner_name=runner.runner_name,
            user=user,
            success=True
        )

        return True

    async def _verify_labels_after_registration(
        self,
        runner_id: str,
        expected_labels: List[str],
        user_identity: str,
        oidc_sub: Optional[str],
        delay: int = 60
    ):
        """
        Verify runner labels after registration (Phase 2: Detection).

        This asynchronous task validates that the runner was configured
        with the expected labels. If a violation is detected, the runner
        is automatically deleted and a security event is logged.

        Args:
            runner_id: Internal runner ID
            expected_labels: Labels that should be present
            user_identity: User who provisioned the runner
            oidc_sub: OIDC subject claim
            delay: Seconds to wait before verification
        """
        await asyncio.sleep(delay)

        try:
            # Retrieve runner from database
            runner = self.db.query(Runner).filter(Runner.id == runner_id).first()

            if not runner or runner.status == "deleted":
                # Runner was already deleted
                return

            # Fetch runner from GitHub API
            if not runner.github_runner_id:
                # Runner not yet registered, check by name
                github_runner = await self.github.get_runner_by_name(runner.runner_name)
            else:
                github_runner = await self.github.get_runner_by_id(runner.github_runner_id)

            if not github_runner:
                # Runner not found in GitHub (may still be registering)
                logger.info(
                    "label_verification_skipped",
                    runner_id=runner_id,
                    reason="runner_not_found_in_github"
                )
                return

            # Verify labels match
            label_policy_service = LabelPolicyService(self.db)
            mismatched_labels = label_policy_service.verify_labels_match(
                expected_labels=expected_labels,
                actual_labels=github_runner.labels
            )

            if mismatched_labels:
                # SECURITY VIOLATION DETECTED
                logger.error(
                    "label_verification_failed",
                    runner_id=runner_id,
                    runner_name=runner.runner_name,
                    expected_labels=expected_labels,
                    actual_labels=github_runner.labels,
                    mismatched=list(mismatched_labels)
                )

                # Log security event
                label_policy_service.log_security_event(
                    event_type="label_policy_violation",
                    severity="high",
                    user_identity=user_identity,
                    oidc_sub=oidc_sub,
                    runner_id=runner_id,
                    runner_name=runner.runner_name,
                    github_runner_id=github_runner.id,
                    violation_data={
                        "expected_labels": expected_labels,
                        "actual_labels": github_runner.labels,
                        "mismatched_labels": list(mismatched_labels),
                        "verification_method": "post_registration"
                    },
                    action_taken="runner_deleted"
                )

                # Delete runner from GitHub
                try:
                    await self.github.delete_runner(github_runner.id)
                    logger.info(
                        "violating_runner_deleted",
                        runner_id=runner_id,
                        github_runner_id=github_runner.id
                    )
                except Exception as delete_error:
                    logger.error(
                        "failed_to_delete_violating_runner",
                        runner_id=runner_id,
                        error=str(delete_error)
                    )

                # Update local state
                runner.status = "deleted"
                runner.deleted_at = datetime.utcnow()
                self.db.commit()

            else:
                # Labels match - verification successful
                logger.info(
                    "label_verification_passed",
                    runner_id=runner_id,
                    runner_name=runner.runner_name
                )

        except Exception as e:
            logger.exception(
                "label_verification_error",
                runner_id=runner_id,
                error=str(e)
            )

    def _log_audit(
        self,
        event_type: str,
        user: AuthenticatedUser,
        success: bool,
        runner_id: Optional[str] = None,
        runner_name: Optional[str] = None,
        error_message: Optional[str] = None,
        event_data: Optional[dict] = None
    ):
        """Log an audit event."""
        audit = AuditLog(
            event_type=event_type,
            runner_id=runner_id,
            runner_name=runner_name,
            user_identity=user.identity,
            oidc_sub=user.sub,
            success=success,
            error_message=error_message,
            event_data=json.dumps(event_data) if event_data else None
        )

        self.db.add(audit)
        self.db.commit()
