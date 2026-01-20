"""Tests for runner API endpoints.

Includes regression tests for fixed bugs:
- Delete runner returns 500 instead of 404 for wrong user (fixed)
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Runner


class TestRunnerEndpointsAuthentication:
    """Tests for runner endpoint authentication."""

    def test_provision_runner_requires_auth(self, client: TestClient, test_db: Session):
        """Test that provisioning requires authentication."""
        response = client.post(
            "/api/v1/runners/provision",
            json={"runner_name": "test-runner", "labels": ["test"]},
        )
        assert response.status_code in [401, 403]

    def test_list_runners_requires_auth(self, client: TestClient, test_db: Session):
        """Test that listing runners requires authentication."""
        response = client.get("/api/v1/runners")
        assert response.status_code in [401, 403]

    def test_get_runner_requires_auth(self, client: TestClient, test_db: Session):
        """Test that getting a runner requires authentication."""
        response = client.get("/api/v1/runners/some-id")
        assert response.status_code in [401, 403]

    def test_delete_runner_requires_auth(self, client: TestClient, test_db: Session):
        """Test that deleting a runner requires authentication."""
        response = client.delete("/api/v1/runners/some-id")
        assert response.status_code in [401, 403]


class TestListRunners:
    """Tests for listing runners."""

    def test_list_runners_empty(
        self, client: TestClient, test_db: Session, auth_override
    ):
        """Test listing runners when none exist."""
        response = client.get("/api/v1/runners")
        assert response.status_code == 200

        data = response.json()
        assert data["runners"] == []
        assert data["total"] == 0

    def test_list_runners_returns_only_user_runners(
        self, client: TestClient, test_db: Session, auth_override, mock_user
    ):
        """Test that listing runners only returns the authenticated user's runners."""
        # Create runner for current user
        user_runner = Runner(
            runner_name="my-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by=mock_user.identity,
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(user_runner)

        # Create runner for different user
        other_runner = Runner(
            runner_name="other-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by="other@example.com",
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(other_runner)
        test_db.commit()

        response = client.get("/api/v1/runners")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert len(data["runners"]) == 1
        assert data["runners"][0]["runner_name"] == "my-runner"

    def test_list_runners_excludes_deleted(
        self, client: TestClient, test_db: Session, auth_override, mock_user
    ):
        """Test that deleted runners are not listed."""
        # Create active runner
        active_runner = Runner(
            runner_name="active-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by=mock_user.identity,
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(active_runner)

        # Create deleted runner
        deleted_runner = Runner(
            runner_name="deleted-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by=mock_user.identity,
            status="deleted",
            deleted_at=datetime.now(timezone.utc),
            github_url="https://github.com/test-org",
        )
        test_db.add(deleted_runner)
        test_db.commit()

        response = client.get("/api/v1/runners")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 1
        assert data["runners"][0]["runner_name"] == "active-runner"


class TestGetRunner:
    """Tests for getting a specific runner."""

    def test_get_runner_success(
        self, client: TestClient, test_db: Session, auth_override, mock_user
    ):
        """Test getting a runner by ID."""
        runner = Runner(
            runner_name="my-runner",
            runner_group_id=1,
            labels=json.dumps(["test", "linux"]),
            provisioned_by=mock_user.identity,
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        response = client.get(f"/api/v1/runners/{runner.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["runner_name"] == "my-runner"
        assert data["status"] == "active"
        assert data["labels"] == ["test", "linux"]

    def test_get_runner_not_found(
        self, client: TestClient, test_db: Session, auth_override
    ):
        """Test getting a non-existent runner."""
        response = client.get("/api/v1/runners/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_get_runner_wrong_user(
        self, client: TestClient, test_db: Session, auth_override
    ):
        """Test that users cannot access other users' runners."""
        # Create runner owned by different user
        runner = Runner(
            runner_name="other-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by="other@example.com",
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        response = client.get(f"/api/v1/runners/{runner.id}")
        assert response.status_code == 404


class TestDeleteRunner:
    """Tests for deleting runners.

    Includes regression test for: delete runner returns 500 instead of 404 for wrong user
    """

    def test_delete_runner_not_found_returns_404(
        self, client: TestClient, test_db: Session, auth_override
    ):
        """Test deleting a non-existent runner returns 404."""
        response = client.delete("/api/v1/runners/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_runner_wrong_user_returns_404_not_500(
        self, client: TestClient, test_db: Session, auth_override
    ):
        """
        REGRESSION TEST: Delete runner owned by different user should return 404, not 500.

        Previously, the code had HTTPException raised inside a try/except block that
        caught all exceptions, causing it to be re-raised as a 500 error.

        Fix: Move the runner existence check and HTTPException outside the try/except.
        See: app/api/v1/runners.py:220-228
        """
        # Create runner owned by different user
        runner = Runner(
            runner_name="other-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by="other@example.com",  # Different from auth_override user
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        response = client.delete(f"/api/v1/runners/{runner.id}")

        # REGRESSION: This should be 404, not 500
        assert response.status_code == 404, (
            "Expected 404 Not Found when deleting another user's runner, "
            f"got {response.status_code}. "
            "This is a regression of the '500 instead of 404' bug."
        )
        assert "not found" in response.json()["detail"].lower()

    def test_delete_runner_success(
        self, client: TestClient, test_db: Session, auth_override, mock_user
    ):
        """Test successfully deleting a runner."""
        # Create runner owned by current user
        runner = Runner(
            runner_name="my-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by=mock_user.identity,
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)
        runner_id = runner.id

        # Mock the GitHub client to avoid actual API calls
        with patch("app.services.runner_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github.delete_runner = AsyncMock(return_value=True)
            MockGitHubClient.return_value = mock_github

            response = client.delete(f"/api/v1/runners/{runner_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["runner_name"] == "my-runner"

    def test_delete_already_deleted_runner(
        self, client: TestClient, test_db: Session, auth_override, mock_user
    ):
        """Test deleting an already deleted runner."""
        runner = Runner(
            runner_name="deleted-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by=mock_user.identity,
            status="deleted",
            deleted_at=datetime.now(timezone.utc),
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        with patch("app.services.runner_service.GitHubClient"):
            response = client.delete(f"/api/v1/runners/{runner.id}")

        # Should return 400 because runner is already deleted
        assert response.status_code == 400
        assert "already deleted" in response.json()["detail"].lower()

    def test_delete_runner_by_oidc_sub_when_identity_differs(
        self, client: TestClient, test_db: Session, mock_user
    ):
        """
        REGRESSION TEST: User should be able to delete runners provisioned by them
        even when their OIDC token has different claims.

        Scenario: User provisions runner with email-based identity, then tries to
        delete with M2M token that only has 'sub' claim. The ownership check should
        match on oidc_sub as well as provisioned_by.

        Fix: get_runner_by_id now checks both provisioned_by == user.identity
        OR oidc_sub == user.sub for ownership.
        """
        from app.auth.dependencies import get_current_user
        from app.main import app

        # Runner was provisioned with email identity
        runner = Runner(
            runner_name="sub-match-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by="different-identity@example.com",  # Different from user.identity
            oidc_sub=mock_user.sub,  # But same OIDC sub
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)
        runner_id = runner.id

        # Override auth to use mock_user (whose sub matches oidc_sub)
        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            with patch("app.services.runner_service.GitHubClient") as MockGitHubClient:
                mock_github = AsyncMock()
                mock_github.delete_runner = AsyncMock(return_value=True)
                MockGitHubClient.return_value = mock_github

                response = client.delete(f"/api/v1/runners/{runner_id}")

            # Should be able to delete because oidc_sub matches
            assert response.status_code == 200, (
                f"Expected 200 OK when deleting runner by OIDC sub match, "
                f"got {response.status_code}: {response.json()}"
            )
            data = response.json()
            assert data["success"] is True
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestRefreshRunner:
    """Tests for refreshing runner status."""

    def test_refresh_runner_not_found(
        self, client: TestClient, test_db: Session, auth_override
    ):
        """Test refreshing a non-existent runner."""
        response = client.post(
            "/api/v1/runners/00000000-0000-0000-0000-000000000000/refresh"
        )
        assert response.status_code == 404

    def test_refresh_runner_success(
        self, client: TestClient, test_db: Session, auth_override, mock_user
    ):
        """Test successfully refreshing a runner's status."""
        runner = Runner(
            runner_name="my-runner",
            runner_group_id=1,
            labels=json.dumps(["test"]),
            provisioned_by=mock_user.identity,
            status="pending",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        # Mock GitHub client
        with patch("app.services.runner_service.GitHubClient") as MockGitHubClient:
            mock_github = AsyncMock()
            mock_github_runner = MagicMock()
            mock_github_runner.id = 12345
            mock_github_runner.status = "online"
            mock_github.get_runner_by_name = AsyncMock(return_value=mock_github_runner)
            MockGitHubClient.return_value = mock_github

            response = client.post(f"/api/v1/runners/{runner.id}/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["github_runner_id"] == 12345
