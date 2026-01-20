"""Tests for GitHub sync service."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.orm import Session

from app.models import LabelPolicy, Runner, SecurityEvent
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
            # Mock GitHub runner - labels match what was provisioned
            mock_github_runner = MagicMock()
            mock_github_runner.id = 12345
            mock_github_runner.name = "test-runner"
            mock_github_runner.status = "online"
            mock_github_runner.labels = ["self-hosted", "linux", "test"]

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
            mock_github_runner.labels = ["self-hosted", "linux", "test"]

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


class TestLabelPolicyEnforcement:
    """Tests for label policy enforcement during sync."""

    def test_sync_runner_with_policy_violation_deletes_runner(
        self, test_db: Session, mock_settings
    ):
        """Test sync deletes runner when labels violate policy."""
        # Create a label policy that only allows "allowed-label"
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["allowed-label"]),
            label_patterns=None,
        )
        test_db.add(policy)

        # Create a runner provisioned by that user
        runner = Runner(
            runner_name="policy-violation-runner",
            runner_group_id=1,
            labels=json.dumps(["allowed-label"]),
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
            # Mock GitHub runner with DIFFERENT labels than allowed
            mock_github_runner = MagicMock()
            mock_github_runner.id = 12345
            mock_github_runner.name = "policy-violation-runner"
            mock_github_runner.status = "online"
            mock_github_runner.labels = ["self-hosted", "linux", "forbidden-label"]

            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[mock_github_runner])
            mock_github.delete_runner = AsyncMock(return_value=True)
            MockGitHubClient.return_value = mock_github

            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_all_runners()
            )

            # Should have one policy violation and one deletion
            assert result.policy_violations == 1
            assert result.deleted == 1

            # Verify runner was marked deleted
            test_db.refresh(runner)
            assert runner.status == "deleted"
            assert runner.deleted_at is not None

            # Verify delete_runner was called on GitHub
            mock_github.delete_runner.assert_called_once_with(12345)

            # Verify security event was logged
            event = (
                test_db.query(SecurityEvent)
                .filter(SecurityEvent.event_type == "label_policy_violation")
                .first()
            )
            assert event is not None
            assert event.user_identity == "user@example.com"
            assert event.runner_name == "policy-violation-runner"
            assert event.action_taken == "runner_deleted"

    def test_sync_runner_with_valid_labels_not_deleted(
        self, test_db: Session, mock_settings
    ):
        """Test sync does not delete runner when labels are valid."""
        # Create a label policy that allows "valid-label"
        policy = LabelPolicy(
            user_identity="user@example.com",
            allowed_labels=json.dumps(["valid-label"]),
            label_patterns=None,
        )
        test_db.add(policy)

        # Create a runner provisioned by that user
        runner = Runner(
            runner_name="valid-runner",
            runner_group_id=1,
            labels=json.dumps(["valid-label"]),
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
            # Mock GitHub runner with valid labels (system labels are ignored)
            mock_github_runner = MagicMock()
            mock_github_runner.id = 12345
            mock_github_runner.name = "valid-runner"
            mock_github_runner.status = "online"
            mock_github_runner.labels = ["self-hosted", "linux", "valid-label"]

            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[mock_github_runner])
            MockGitHubClient.return_value = mock_github

            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_all_runners()
            )

            # No violations
            assert result.policy_violations == 0
            assert result.deleted == 0
            assert result.unchanged == 1

            # Verify runner still exists
            test_db.refresh(runner)
            assert runner.status == "online"

    def test_sync_runner_no_policy_allows_all_labels(
        self, test_db: Session, mock_settings
    ):
        """Test sync allows any labels when no policy exists for user."""
        # No policy for this user

        # Create a runner
        runner = Runner(
            runner_name="no-policy-runner",
            runner_group_id=1,
            labels=json.dumps(["any-label"]),
            provisioned_by="nopolicy@example.com",
            status="online",
            github_runner_id=12345,
            github_url="https://github.com/test-org",
            registered_at=datetime.now(timezone.utc),
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            # Mock GitHub runner with any labels
            mock_github_runner = MagicMock()
            mock_github_runner.id = 12345
            mock_github_runner.name = "no-policy-runner"
            mock_github_runner.status = "online"
            mock_github_runner.labels = ["self-hosted", "linux", "random-label"]

            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[mock_github_runner])
            MockGitHubClient.return_value = mock_github

            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_all_runners()
            )

            # No violations - permissive by default when no policy
            assert result.policy_violations == 0
            assert result.deleted == 0

    def test_sync_runner_wildcard_policy_allows_all(
        self, test_db: Session, mock_settings
    ):
        """Test sync allows any labels when policy has wildcard."""
        # Create a wildcard policy
        policy = LabelPolicy(
            user_identity="admin@example.com",
            allowed_labels=json.dumps(["*"]),
            label_patterns=None,
        )
        test_db.add(policy)

        # Create a runner
        runner = Runner(
            runner_name="wildcard-runner",
            runner_group_id=1,
            labels=json.dumps(["any"]),
            provisioned_by="admin@example.com",
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
            mock_github_runner.name = "wildcard-runner"
            mock_github_runner.status = "online"
            mock_github_runner.labels = ["self-hosted", "any-label-allowed"]

            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[mock_github_runner])
            MockGitHubClient.return_value = mock_github

            service = SyncService(mock_settings, test_db)

            import asyncio

            result = asyncio.get_event_loop().run_until_complete(
                service.sync_all_runners()
            )

            # No violations with wildcard
            assert result.policy_violations == 0
