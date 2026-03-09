"""GitHub runner synchronization service."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.config import Settings
from app.github.client import GitHubClient, GitHubRunnerInfo
from app.models import Runner
from app.services.label_policy_service import LabelPolicyService

logger = structlog.get_logger()


@dataclass
class SyncResult:
    """Result of a sync operation."""

    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    errors: int = 0
    policy_violations: int = 0
    label_drifts: int = 0  # JIT runners with labels changed after provisioning

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/API response."""
        return {
            "updated": self.updated,
            "deleted": self.deleted,
            "unchanged": self.unchanged,
            "errors": self.errors,
            "policy_violations": self.policy_violations,
            "label_drifts": self.label_drifts,
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
                    # Check for label drift on JIT runners
                    drift_handled = await self._check_label_drift(runner, github_runner)
                    if drift_handled:
                        result.label_drifts += 1
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

        return changed

    def _is_token_expired(self, runner: Runner) -> bool:
        """Check if a pending runner's JIT config has expired (1 hour after creation)."""
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        return runner.created_at.replace(tzinfo=timezone.utc) < cutoff

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

    async def cleanup_expired_tokens(self) -> int:
        """
        Mark stale pending JIT runners as deleted (JIT config expires after 1 hour).

        Returns:
            Number of runners cleaned up
        """
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        expired_runners = (
            self.db.query(Runner)
            .filter(
                Runner.status == "pending",
                Runner.created_at < cutoff,
            )
            .all()
        )

        count = 0
        for runner in expired_runners:
            self._mark_deleted(runner, reason="jit_config_expired")
            count += 1

        if count > 0:
            self.db.commit()
            logger.info("stale_pending_runners_cleaned", count=count)

        return count

    async def _check_label_drift(
        self, runner: Runner, github_runner: GitHubRunnerInfo
    ) -> bool:
        """
        Check for label drift on JIT-provisioned runners.

        Label drift occurs when a JIT runner's labels have been modified
        after provisioning. This is a security concern because JIT provisioning
        is supposed to enforce labels server-side.

        Args:
            runner: Local runner record
            github_runner: GitHub runner info with current labels

        Returns:
            True if drift was detected and handled (runner deleted), False otherwise
        """
        # Skip if no labels stored
        if not runner.labels:
            return False

        # Parse original labels
        try:
            original_labels = set(json.loads(runner.labels))
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "invalid_runner_labels",
                runner_id=runner.id,
                runner_name=runner.runner_name,
            )
            return False

        # Compare with current labels
        current_labels = set(github_runner.labels)

        # Check for drift (labels added or removed)
        added_labels = current_labels - original_labels
        removed_labels = original_labels - current_labels

        if not added_labels and not removed_labels:
            # No drift detected
            return False

        # LABEL DRIFT DETECTED
        logger.error(
            "label_drift_detected",
            runner_id=runner.id,
            runner_name=runner.runner_name,
            github_runner_id=github_runner.id,
            original_labels=list(original_labels),
            current_labels=list(current_labels),
            added_labels=list(added_labels),
            removed_labels=list(removed_labels),
            runner_busy=github_runner.busy,
        )

        # Check if runner is busy and we should skip deletion
        if github_runner.busy and not self.settings.label_drift_delete_busy_runners:
            logger.warning(
                "label_drift_skipped_busy_runner",
                runner_id=runner.id,
                runner_name=runner.runner_name,
                github_runner_id=github_runner.id,
            )
            # Log security event but don't delete
            self.label_policy_service.log_security_event(
                event_type="label_drift_detected",
                severity="high",
                user_identity=runner.provisioned_by,
                runner_id=str(runner.id),
                runner_name=runner.runner_name,
                github_runner_id=github_runner.id,
                violation_data={
                    "original_labels": list(original_labels),
                    "current_labels": list(current_labels),
                    "added_labels": list(added_labels),
                    "removed_labels": list(removed_labels),
                    "runner_busy": True,
                    "provisioning_method": "jit",
                },
                action_taken="logged_only",
            )
            return False

        # Delete the runner from GitHub
        try:
            deleted = await self.github.delete_runner(github_runner.id)
            if deleted:
                logger.info(
                    "runner_deleted_for_label_drift",
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
                "failed_to_delete_drifted_runner",
                runner_id=runner.id,
                github_runner_id=github_runner.id,
                error=str(e),
            )

        # Log security event
        self.label_policy_service.log_security_event(
            event_type="label_drift_detected",
            severity="high",
            user_identity=runner.provisioned_by,
            runner_id=str(runner.id),
            runner_name=runner.runner_name,
            github_runner_id=github_runner.id,
            violation_data={
                "original_labels": list(original_labels),
                "current_labels": list(current_labels),
                "added_labels": list(added_labels),
                "removed_labels": list(removed_labels),
                "runner_busy": github_runner.busy,
                "provisioning_method": "jit",
            },
            action_taken="runner_deleted",
        )

        # Mark runner as deleted in local DB
        self._mark_deleted(runner, reason="label_drift")
        return True
