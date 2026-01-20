"""GitHub runner synchronization service."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.config import Settings
from app.github.client import GitHubClient
from app.models import Runner
from app.services.label_policy_service import LabelPolicyService, LabelPolicyViolation

logger = structlog.get_logger()


@dataclass
class SyncResult:
    """Result of a sync operation."""

    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    errors: int = 0
    policy_violations: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/API response."""
        return {
            "updated": self.updated,
            "deleted": self.deleted,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "policy_violations": self.policy_violations,
            "total": self.updated + self.deleted + self.unchanged + self.errors,
        }


class SyncError(Exception):
    """Base exception for sync errors."""

    pass


class SyncRateLimitedError(SyncError):
    """Raised when GitHub API rate limit is exceeded."""

    pass


class SyncNetworkError(SyncError):
    """Raised when network error occurs during sync."""

    pass


class SyncService:
    """Service for synchronizing runner state with GitHub."""

    def __init__(self, settings: Settings, db: Session):
        self.settings = settings
        self.db = db
        self.github = GitHubClient(settings)
        self.label_policy_service = LabelPolicyService(db)

    async def sync_all_runners(self) -> SyncResult:
        """
        Sync all non-deleted runners with GitHub.

        Fetches current runner state from GitHub and updates local database
        to match. Runners not found in GitHub are marked as deleted.

        Returns:
            SyncResult with counts of updated, deleted, unchanged runners

        Raises:
            SyncRateLimitedError: If GitHub API rate limit exceeded
            SyncNetworkError: If network error occurs
        """
        import httpx

        result = SyncResult()

        # Get all non-deleted local runners
        local_runners = self.db.query(Runner).filter(Runner.status != "deleted").all()

        if not local_runners:
            logger.info("sync_skipped", reason="no_runners_to_sync")
            return result

        logger.info("sync_started", runner_count=len(local_runners))

        # Fetch all runners from GitHub (single API call)
        try:
            github_runners = await self.github.list_runners()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.error("sync_rate_limited")
                raise SyncRateLimitedError("GitHub API rate limit exceeded")
            logger.error("sync_github_error", status_code=e.response.status_code)
            raise SyncError(f"GitHub API error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("sync_network_error", error=str(e))
            raise SyncNetworkError(f"Network error: {str(e)}")

        # Build lookup by name for efficient matching
        github_by_name = {r.name: r for r in github_runners}

        # Process each local runner
        for runner in local_runners:
            try:
                github_runner = github_by_name.get(runner.runner_name)

                if github_runner:
                    # Runner exists in GitHub - check label policy first
                    violation = await self._check_label_policy(
                        runner, github_runner.labels
                    )
                    if violation:
                        # Policy violation - delete runner from GitHub
                        await self._handle_policy_violation(
                            runner, github_runner, violation
                        )
                        result.policy_violations += 1
                        result.deleted += 1
                    elif self._update_runner_from_github(runner, github_runner):
                        result.updated += 1
                    else:
                        result.unchanged += 1
                else:
                    # Runner not found in GitHub
                    if runner.status == "pending":
                        # Still pending - check if token expired
                        if self._is_token_expired(runner):
                            self._mark_deleted(
                                runner, reason="registration_token_expired"
                            )
                            result.deleted += 1
                        else:
                            result.unchanged += 1
                    else:
                        # Was registered, now gone - mark deleted
                        self._mark_deleted(runner, reason="not_found_in_github")
                        result.deleted += 1

            except Exception as e:
                logger.error(
                    "sync_runner_error",
                    runner_id=runner.id,
                    runner_name=runner.runner_name,
                    error=str(e),
                )
                result.errors += 1

        self.db.commit()

        logger.info("sync_completed", **result.to_dict())
        return result

    async def sync_runner(self, runner_id: str) -> Optional[Runner]:
        """
        Sync a single runner with GitHub.

        Args:
            runner_id: Internal runner UUID

        Returns:
            Updated runner or None if not found
        """
        runner = self.db.query(Runner).filter(Runner.id == runner_id).first()

        if not runner:
            return None

        if runner.status == "deleted":
            return runner

        # Fetch from GitHub
        github_runner = await self.github.get_runner_by_name(runner.runner_name)

        if github_runner:
            self._update_runner_from_github(runner, github_runner)
        elif runner.status != "pending":
            self._mark_deleted(runner, reason="not_found_in_github")

        self.db.commit()
        return runner

    def _update_runner_from_github(self, runner: Runner, github_runner) -> bool:
        """
        Update local runner state from GitHub runner info.

        Args:
            runner: Local runner model
            github_runner: GitHub runner info

        Returns:
            True if runner was updated, False if unchanged
        """
        changed = False
        old_status = runner.status

        # Update status
        new_status = github_runner.status  # 'online' or 'offline'
        if runner.status != new_status:
            runner.status = new_status
            changed = True
            logger.info(
                "runner_status_changed",
                runner_id=runner.id,
                runner_name=runner.runner_name,
                old_status=old_status,
                new_status=new_status,
            )

        # Update GitHub runner ID
        if runner.github_runner_id != github_runner.id:
            runner.github_runner_id = github_runner.id
            changed = True

        # Set registered_at if not set
        if runner.registered_at is None:
            runner.registered_at = datetime.now(timezone.utc)
            changed = True

        # Clear registration token after successful registration
        if runner.registration_token:
            runner.registration_token = None
            runner.registration_token_expires_at = None
            changed = True

        return changed

    def _is_token_expired(self, runner: Runner) -> bool:
        """Check if runner's registration token has expired."""
        if not runner.registration_token_expires_at:
            # No expiry set - consider expired after cleanup hours
            from datetime import timedelta

            cutoff = datetime.now(timezone.utc) - timedelta(
                hours=self.settings.cleanup_stale_runners_hours
            )
            return runner.created_at.replace(tzinfo=timezone.utc) < cutoff

        # Check actual expiry
        expiry = runner.registration_token_expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry < datetime.now(timezone.utc)

    def _mark_deleted(self, runner: Runner, reason: str) -> None:
        """Mark a runner as deleted."""
        logger.warning(
            "runner_marked_deleted",
            runner_id=runner.id,
            runner_name=runner.runner_name,
            previous_status=runner.status,
            reason=reason,
        )
        runner.status = "deleted"
        runner.deleted_at = datetime.now(timezone.utc)
        runner.registration_token = None
        runner.registration_token_expires_at = None

    async def cleanup_expired_tokens(self) -> int:
        """
        Clear expired registration tokens from pending runners.

        Returns:
            Number of tokens cleared
        """
        now = datetime.now(timezone.utc)
        expired_runners = (
            self.db.query(Runner)
            .filter(
                Runner.status == "pending",
                Runner.registration_token.isnot(None),
                Runner.registration_token_expires_at < now,
            )
            .all()
        )

        count = 0
        for runner in expired_runners:
            runner.registration_token = None
            runner.registration_token_expires_at = None
            count += 1

        if count > 0:
            self.db.commit()
            logger.info("expired_tokens_cleared", count=count)

        return count

    async def _check_label_policy(
        self, runner: Runner, actual_labels: list[str]
    ) -> Optional[LabelPolicyViolation]:
        """
        Check if runner's labels comply with user's label policy.

        Args:
            runner: Local runner record
            actual_labels: Labels configured on the GitHub runner

        Returns:
            LabelPolicyViolation if policy violated, None otherwise
        """
        try:
            self.label_policy_service.validate_labels(
                runner.provisioned_by, actual_labels
            )
            return None
        except LabelPolicyViolation as e:
            return e

    async def _handle_policy_violation(
        self, runner: Runner, github_runner, violation: LabelPolicyViolation
    ) -> None:
        """
        Handle a label policy violation by deleting the runner and logging.

        Args:
            runner: Local runner record
            github_runner: GitHub runner info
            violation: The policy violation details
        """
        logger.error(
            "label_policy_violation_detected",
            runner_id=runner.id,
            runner_name=runner.runner_name,
            github_runner_id=github_runner.id,
            provisioned_by=runner.provisioned_by,
            actual_labels=github_runner.labels,
            invalid_labels=list(violation.invalid_labels),
        )

        # Delete the runner from GitHub
        try:
            deleted = await self.github.delete_runner(github_runner.id)
            if deleted:
                logger.info(
                    "runner_deleted_for_policy_violation",
                    runner_id=runner.id,
                    runner_name=runner.runner_name,
                    github_runner_id=github_runner.id,
                )
            else:
                logger.warning(
                    "runner_not_found_for_deletion",
                    runner_id=runner.id,
                    github_runner_id=github_runner.id,
                )
        except Exception as e:
            logger.error(
                "failed_to_delete_runner",
                runner_id=runner.id,
                github_runner_id=github_runner.id,
                error=str(e),
            )

        # Log security event
        self.label_policy_service.log_security_event(
            event_type="label_policy_violation",
            severity="high",
            user_identity=runner.provisioned_by,
            runner_id=str(runner.id),
            runner_name=runner.runner_name,
            github_runner_id=github_runner.id,
            violation_data={
                "actual_labels": github_runner.labels,
                "invalid_labels": list(violation.invalid_labels),
                "message": str(violation),
            },
            action_taken="runner_deleted",
        )

        # Mark runner as deleted in local DB
        self._mark_deleted(runner, reason="label_policy_violation")
