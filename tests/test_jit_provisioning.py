"""Tests for JIT (Just-In-Time) runner provisioning.

Tests cover:
- JIT API endpoint authentication
- JIT provisioning success cases
- JIT provisioning with label policy enforcement
- JIT schema validation
- Label drift detection in sync service
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.github.client import JitConfigResponse
from app.models import Runner
from app.schemas import JitProvisionRequest


class TestJitEndpointAuthentication:
    """Tests for JIT endpoint authentication."""

    def test_jit_provision_requires_auth(self, client: TestClient, test_db: Session):
        """Test that JIT provisioning requires authentication."""
        response = client.post(
            "/api/v1/runners/jit",
            json={"runner_name": "test-runner", "labels": ["test"]},
        )
        assert response.status_code in [401, 403]


class TestJitProvisionRequest:
    """Tests for JIT provision request schema validation."""

    def test_valid_request_with_runner_name(self):
        """Test valid request with exact runner name."""
        request = JitProvisionRequest(runner_name="test-runner", labels=["test"])
        assert request.runner_name == "test-runner"
        assert request.labels == ["test"]
        assert request.work_folder == "_work"

    def test_valid_request_with_prefix(self):
        """Test valid request with runner name prefix."""
        request = JitProvisionRequest(runner_name_prefix="my-prefix", labels=["test"])
        assert request.runner_name_prefix == "my-prefix"
        assert request.runner_name is None

    def test_invalid_request_missing_name(self):
        """Test that request without runner_name or runner_name_prefix is invalid."""
        with pytest.raises(ValueError, match="Either.*runner_name.*must be provided"):
            JitProvisionRequest(labels=["test"])

    def test_invalid_request_both_names(self):
        """Test that request with both runner_name and runner_name_prefix is invalid."""
        with pytest.raises(ValueError, match="Only one of"):
            JitProvisionRequest(
                runner_name="test", runner_name_prefix="prefix", labels=["test"]
            )

    def test_invalid_runner_name_format(self):
        """Test that invalid runner name format is rejected."""
        with pytest.raises(ValueError, match="alphanumeric"):
            JitProvisionRequest(runner_name="invalid name!", labels=["test"])

    def test_invalid_label_format(self):
        """Test that invalid label format is rejected."""
        with pytest.raises(ValueError, match="alphanumeric"):
            JitProvisionRequest(runner_name="test-runner", labels=["bad label!"])


class TestJitProvisionEndpoint:
    """Tests for JIT provisioning endpoint."""

    def test_jit_provision_success(
        self,
        client: TestClient,
        test_db: Session,
        auth_override,
        mock_user,
        test_team,
        test_team_membership,
    ):
        """Test successful JIT provisioning."""
        mock_jit_response = JitConfigResponse(
            runner_id=12345,
            runner_name="test-runner",
            encoded_jit_config="base64encodedconfig==",
            os="linux",
            labels=["self-hosted", "linux", "x64", "test"],
        )

        with patch("app.services.runner_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.generate_jit_config = AsyncMock(return_value=mock_jit_response)
            MockGitHubClient.return_value = mock_github

            response = client.post(
                "/api/v1/runners/jit",
                json={"runner_name": "test-runner", "labels": ["test"]},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["runner_name"] == "test-runner"
        assert data["encoded_jit_config"] == "base64encodedconfig=="
        assert "self-hosted" in data["labels"]
        assert "./run.sh --jitconfig" in data["run_command"]

        # Verify runner was created in database
        runner = (
            test_db.query(Runner).filter(Runner.runner_name == "test-runner").first()
        )
        assert runner is not None
        assert runner.provisioning_method == "jit"
        assert runner.ephemeral is True
        assert runner.github_runner_id == 12345

    def test_jit_provision_with_prefix(
        self,
        client: TestClient,
        test_db: Session,
        auth_override,
        mock_user,
        test_team,
        test_team_membership,
    ):
        """Test JIT provisioning with runner name prefix."""
        mock_jit_response = JitConfigResponse(
            runner_id=12345,
            runner_name="my-prefix-abc123",
            encoded_jit_config="base64encodedconfig==",
            os="linux",
            labels=["self-hosted", "linux", "x64"],
        )

        with patch("app.services.runner_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.generate_jit_config = AsyncMock(return_value=mock_jit_response)
            MockGitHubClient.return_value = mock_github

            response = client.post(
                "/api/v1/runners/jit",
                json={"runner_name_prefix": "my-prefix", "labels": ["test"]},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["runner_name"].startswith("my-prefix-")

    def test_jit_provision_duplicate_name_fails(
        self, client: TestClient, test_db: Session, auth_override, mock_user
    ):
        """Test that JIT provisioning fails for duplicate active runner name."""
        # Create existing active runner
        existing_runner = Runner(
            runner_name="existing-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by=mock_user.identity,
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(existing_runner)
        test_db.commit()

        with patch("app.services.runner_service.GitHubClient"):
            response = client.post(
                "/api/v1/runners/jit",
                json={"runner_name": "existing-runner", "labels": ["test"]},
            )

        assert response.status_code == 400
        assert "currently active" in response.json()["detail"].lower()

    def test_jit_provision_label_policy_violation(
        self,
        client: TestClient,
        test_db: Session,
        auth_override,
        mock_user,
        test_team,
        test_team_membership,
    ):
        """Test that JIT provisioning enforces label policies."""
        # Update team with restrictive label policy
        test_team.required_labels = json.dumps(["allowed-label"])
        test_team.optional_label_patterns = json.dumps([])
        test_db.commit()

        with patch("app.services.runner_service.GitHubClient"):
            response = client.post(
                "/api/v1/runners/jit",
                json={"runner_name": "test-runner", "labels": ["forbidden-label"]},
            )

        assert response.status_code == 403
        detail = response.json()["detail"].lower()
        assert "missing required labels" in detail or "not permitted" in detail


class TestJitLabelDriftDetection:
    """Tests for label drift detection in sync service."""

    def test_label_drift_detected_idle_runner(self, test_db: Session, mock_settings):
        """Test that label drift is detected on idle JIT runners."""
        from app.services.sync_service import SyncService

        # Create JIT runner with original labels
        runner = Runner(
            runner_name="jit-runner",
            runner_group_id=1,
            labels=json.dumps(["self-hosted", "linux", "x64", "gpu"]),
            provisioned_by="test@example.com",
            status="online",
            github_runner_id=12345,
            provisioning_method="jit",
            provisioned_labels=json.dumps(["self-hosted", "linux", "x64", "gpu"]),
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()

        # Create mock GitHub runner with DIFFERENT labels (drift!)
        mock_github_runner = MagicMock()
        mock_github_runner.id = 12345
        mock_github_runner.name = "jit-runner"
        mock_github_runner.status = "online"
        mock_github_runner.busy = False  # Idle
        mock_github_runner.labels = [
            "self-hosted",
            "linux",
            "x64",
            "unauthorized-label",
        ]

        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[mock_github_runner])
            mock_github.delete_runner = AsyncMock(return_value=True)
            MockGitHubClient.return_value = mock_github

            sync_service = SyncService(mock_settings, test_db)

            # Mock label policy service to not raise violation for allowed labels
            with patch.object(
                sync_service.label_policy_service,
                "validate_labels",
                return_value=None,
            ):
                import asyncio

                result = asyncio.get_event_loop().run_until_complete(
                    sync_service.sync_all_runners()
                )

        assert result.label_drifts == 1
        assert result.deleted == 1

        # Verify runner was marked as deleted
        test_db.refresh(runner)
        assert runner.status == "deleted"

    def test_no_drift_for_registration_token_runners(
        self, test_db: Session, mock_settings
    ):
        """Test that label drift is NOT checked for registration token runners."""
        from app.services.sync_service import SyncService

        # Create registration token runner (not JIT)
        runner = Runner(
            runner_name="reg-token-runner",
            runner_group_id=1,
            labels=json.dumps(["original-label"]),
            provisioned_by="test@example.com",
            status="online",
            github_runner_id=12345,
            provisioning_method="registration_token",  # Not JIT
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()

        # Create mock GitHub runner with different labels
        mock_github_runner = MagicMock()
        mock_github_runner.id = 12345
        mock_github_runner.name = "reg-token-runner"
        mock_github_runner.status = "online"
        mock_github_runner.busy = False
        mock_github_runner.labels = ["different-label"]

        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[mock_github_runner])
            MockGitHubClient.return_value = mock_github

            sync_service = SyncService(mock_settings, test_db)

            with patch.object(
                sync_service.label_policy_service,
                "validate_labels",
                return_value=None,
            ):
                import asyncio

                result = asyncio.get_event_loop().run_until_complete(
                    sync_service.sync_all_runners()
                )

        # No drift should be detected for registration token runners
        assert result.label_drifts == 0
        assert result.deleted == 0

    def test_busy_runner_drift_not_deleted_by_default(
        self, test_db: Session, mock_settings
    ):
        """Test that busy runners with drift are not deleted by default."""
        from app.services.sync_service import SyncService

        # Ensure setting is False
        mock_settings.label_drift_delete_busy_runners = False

        # Create JIT runner
        runner = Runner(
            runner_name="busy-jit-runner",
            runner_group_id=1,
            labels=json.dumps(["original-label"]),
            provisioned_by="test@example.com",
            status="online",
            github_runner_id=12345,
            provisioning_method="jit",
            provisioned_labels=json.dumps(["original-label"]),
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()

        # Create mock GitHub runner with drift, but BUSY
        mock_github_runner = MagicMock()
        mock_github_runner.id = 12345
        mock_github_runner.name = "busy-jit-runner"
        mock_github_runner.status = "online"
        mock_github_runner.busy = True  # Busy!
        mock_github_runner.labels = ["drifted-label"]

        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[mock_github_runner])
            mock_github.delete_runner = AsyncMock(return_value=True)
            MockGitHubClient.return_value = mock_github

            sync_service = SyncService(mock_settings, test_db)

            with patch.object(
                sync_service.label_policy_service,
                "validate_labels",
                return_value=None,
            ):
                import asyncio

                result = asyncio.get_event_loop().run_until_complete(
                    sync_service.sync_all_runners()
                )

        # Drift detected but not deleted (busy runner)
        assert result.label_drifts == 0  # Returns False because not handled
        assert result.deleted == 0

        # Runner should still be active
        test_db.refresh(runner)
        assert runner.status == "online"

    def test_busy_runner_drift_deleted_when_configured(
        self, test_db: Session, mock_settings
    ):
        """Test that busy runners with drift ARE deleted when configured."""
        from app.services.sync_service import SyncService

        # Enable deletion of busy runners with drift
        mock_settings.label_drift_delete_busy_runners = True

        # Create JIT runner
        runner = Runner(
            runner_name="busy-jit-runner-2",
            runner_group_id=1,
            labels=json.dumps(["original-label"]),
            provisioned_by="test@example.com",
            status="online",
            github_runner_id=12346,
            provisioning_method="jit",
            provisioned_labels=json.dumps(["original-label"]),
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()

        # Create mock GitHub runner with drift, and BUSY
        mock_github_runner = MagicMock()
        mock_github_runner.id = 12346
        mock_github_runner.name = "busy-jit-runner-2"
        mock_github_runner.status = "online"
        mock_github_runner.busy = True
        mock_github_runner.labels = ["drifted-label"]

        with patch("app.services.sync_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.list_runners = AsyncMock(return_value=[mock_github_runner])
            mock_github.delete_runner = AsyncMock(return_value=True)
            MockGitHubClient.return_value = mock_github

            sync_service = SyncService(mock_settings, test_db)

            with patch.object(
                sync_service.label_policy_service,
                "validate_labels",
                return_value=None,
            ):
                import asyncio

                result = asyncio.get_event_loop().run_until_complete(
                    sync_service.sync_all_runners()
                )

        # Drift detected AND deleted (busy but config allows)
        assert result.label_drifts == 1
        assert result.deleted == 1

        # Runner should be deleted
        test_db.refresh(runner)
        assert runner.status == "deleted"


class TestJitGitHubClient:
    """Tests for JIT config generation in GitHub client."""

    @pytest.mark.asyncio
    async def test_generate_jit_config_success(self, mock_settings):
        """Test successful JIT config generation."""
        from app.github.client import GitHubClient

        mock_response = {
            "runner": {
                "id": 12345,
                "name": "test-runner",
                "os": "linux",
                "status": "offline",
                "labels": [
                    {"name": "self-hosted"},
                    {"name": "linux"},
                    {"name": "x64"},
                    {"name": "test"},
                ],
            },
            "encoded_jit_config": "base64encodedconfig==",
        }

        with patch("app.github.client.GitHubAppAuth") as MockAuth:
            mock_auth = AsyncMock()
            mock_auth.get_authenticated_headers = AsyncMock(
                return_value={"Authorization": "Bearer token"}
            )
            MockAuth.return_value = mock_auth

            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_response_obj = MagicMock()
                mock_response_obj.json.return_value = mock_response
                mock_response_obj.raise_for_status = MagicMock()
                mock_client.post = AsyncMock(return_value=mock_response_obj)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                MockClient.return_value = mock_client

                client = GitHubClient(mock_settings)
                result = await client.generate_jit_config(
                    name="test-runner",
                    runner_group_id=1,
                    labels=["test"],
                    work_folder="_work",
                )

        assert result.runner_id == 12345
        assert result.runner_name == "test-runner"
        assert result.encoded_jit_config == "base64encodedconfig=="
        assert "self-hosted" in result.labels
        assert "test" in result.labels
