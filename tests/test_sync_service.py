"""Tests for GitHub sync service."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.orm import Session

from app.models import Runner
from app.services.sync_service import SyncResult, SyncService


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = SyncResult(updated=2, deleted=1, unchanged=5, errors=0)
        d = result.to_dict()

        assert d["updated"] == 2
        assert d["deleted"] == 1
        assert d["unchanged"] == 5
        assert d["errors"] == 0
        assert d["total"] == 8

    def test_default_values(self):
        """Test default values are zero."""
        result = SyncResult()
        assert result.updated == 0
        assert result.deleted == 0
        assert result.unchanged == 0
        assert result.errors == 0


class TestSyncService:
    """Tests for SyncService."""

    def test_sync_no_runners(self, test_db: Session, mock_settings):
        """Test sync when no runners exist."""
        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[])
            MockGitHubClient.return_value = mock_github

            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_all_runners()
            )

            assert result.updated == 0
            assert result.deleted == 0
            assert result.unchanged == 0

    def test_sync_runner_found_in_github(self, test_db: Session, mock_settings):
        """Test sync updates runner status when found in GitHub."""
        # Create a pending runner
        runner = Runner(
            runner_name="test-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by="user@example.com",
            status="pending",
            github_url="https://github.com/test-org",
            registration_token="token123",
            registration_token_expires_at=datetime.now(timezone.utc)
            + timedelta(hours=1),
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            # Mock GitHub runner
            mock_github_runner = MagicMock()
            mock_github_runner.id = 12345
            mock_github_runner.name = "test-runner"
            mock_github_runner.status = "online"

            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[mock_github_runner])
            MockGitHubClient.return_value = mock_github

            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_all_runners()
            )

            assert result.updated == 1
            assert result.deleted == 0
            assert result.unchanged == 0

            # Verify runner was updated
            test_db.refresh(runner)
            assert runner.status == "online"
            assert runner.github_runner_id == 12345
            assert runner.registered_at is not None
            assert runner.registration_token is None

    def test_sync_runner_not_found_marks_deleted(self, test_db: Session, mock_settings):
        """Test sync marks runner as deleted when not found in GitHub."""
        # Create an active runner (not pending)
        runner = Runner(
            runner_name="deleted-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by="user@example.com",
            status="online",  # Was registered
            github_runner_id=99999,
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[])  # Runner not found
            MockGitHubClient.return_value = mock_github

            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_all_runners()
            )

            assert result.updated == 0
            assert result.deleted == 1
            assert result.unchanged == 0

            # Verify runner was marked deleted
            test_db.refresh(runner)
            assert runner.status == "deleted"
            assert runner.deleted_at is not None

    def test_sync_pending_runner_with_expired_token(
        self, test_db: Session, mock_settings
    ):
        """Test sync marks pending runner as deleted when token expired."""
        # Create a pending runner with expired token
        runner = Runner(
            runner_name="expired-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by="user@example.com",
            status="pending",
            github_url="https://github.com/test-org",
            registration_token="expired-token",
            registration_token_expires_at=datetime.now(timezone.utc)
            - timedelta(hours=1),  # Expired
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[])
            MockGitHubClient.return_value = mock_github

            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_all_runners()
            )

            assert result.deleted == 1

            # Verify runner was marked deleted
            test_db.refresh(runner)
            assert runner.status == "deleted"

    def test_sync_pending_runner_with_valid_token_unchanged(
        self, test_db: Session, mock_settings
    ):
        """Test sync leaves pending runner unchanged when token still valid."""
        # Create a pending runner with valid token
        runner = Runner(
            runner_name="pending-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by="user@example.com",
            status="pending",
            github_url="https://github.com/test-org",
            registration_token="valid-token",
            registration_token_expires_at=datetime.now(timezone.utc)
            + timedelta(hours=1),  # Still valid
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[])
            MockGitHubClient.return_value = mock_github

            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_all_runners()
            )

            assert result.unchanged == 1
            assert result.deleted == 0

            # Verify runner status unchanged
            test_db.refresh(runner)
            assert runner.status == "pending"

    def test_sync_runner_status_unchanged(self, test_db: Session, mock_settings):
        """Test sync counts unchanged when status matches."""
        # Create an online runner
        runner = Runner(
            runner_name="stable-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by="user@example.com",
            status="online",
            github_runner_id=12345,
            github_url="https://github.com/test-org",
            registered_at=datetime.now(timezone.utc),
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            mock_github_runner = MagicMock()
            mock_github_runner.id = 12345
            mock_github_runner.name = "stable-runner"
            mock_github_runner.status = "online"  # Same status

            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[mock_github_runner])
            MockGitHubClient.return_value = mock_github

            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_all_runners()
            )

            assert result.unchanged == 1
            assert result.updated == 0


class TestSyncSingleRunner:
    """Tests for syncing individual runners."""

    def test_sync_single_runner_not_found(self, test_db: Session, mock_settings):
        """Test syncing non-existent runner returns None."""
        with patch("app.services.sync_service.GitHubClient"):
            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_runner("nonexistent-id")
            )

            assert result is None

    def test_sync_single_runner_already_deleted(self, test_db: Session, mock_settings):
        """Test syncing deleted runner returns without changes."""
        runner = Runner(
            runner_name="deleted-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by="user@example.com",
            status="deleted",
            github_url="https://github.com/test-org",
            deleted_at=datetime.now(timezone.utc),
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        with patch("app.services.sync_service.GitHubClient"):
            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_runner(runner.id)
            )

            assert result is not None
            assert result.status == "deleted"
