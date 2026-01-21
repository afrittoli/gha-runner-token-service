"""Tests for batch admin operations."""

from sqlalchemy.orm import Session

from app.models import Runner, SecurityEvent
from app.services.user_service import UserService


class TestBatchDisableUsers:
    """Tests for POST /api/v1/admin/batch/disable-users endpoint."""

    def test_batch_disable_users_requires_comment(self, client, admin_auth_override):
        """Test that batch disable requires a comment."""
        response = client.post(
            "/api/v1/admin/batch/disable-users",
            json={},  # Missing required comment
        )
        assert response.status_code == 422

    def test_batch_disable_users_comment_min_length(self, client, admin_auth_override):
        """Test that comment must be at least 10 characters."""
        response = client.post(
            "/api/v1/admin/batch/disable-users",
            json={"comment": "short"},
        )
        assert response.status_code == 422

    def test_batch_disable_specific_users(
        self, client, admin_auth_override, test_db: Session
    ):
        """Test disabling specific users by ID."""
        service = UserService(test_db)

        # Create test users
        user1 = service.create_user(email="batch1@example.com")
        user2 = service.create_user(email="batch2@example.com")
        user3 = service.create_user(email="batch3@example.com")

        response = client.post(
            "/api/v1/admin/batch/disable-users",
            json={
                "comment": "Security incident: disabling test accounts",
                "user_ids": [user1.id, user2.id],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "disable_users"
        assert data["affected_count"] == 2
        assert data["comment"] == "Security incident: disabling test accounts"

        # Verify users are disabled
        test_db.refresh(user1)
        test_db.refresh(user2)
        test_db.refresh(user3)
        assert user1.is_active is False
        assert user2.is_active is False
        assert user3.is_active is True  # Not in the list

    def test_batch_disable_excludes_admins_by_default(
        self, client, admin_auth_override, test_db: Session
    ):
        """Test that admin users are excluded by default."""
        service = UserService(test_db)

        # Create admin and regular users (use different email than mock admin)
        admin_user = service.create_user(email="admin2@example.com", is_admin=True)
        regular_user = service.create_user(email="regular@example.com", is_admin=False)

        response = client.post(
            "/api/v1/admin/batch/disable-users",
            json={
                "comment": "Disabling all users for maintenance",
                "user_ids": [admin_user.id, regular_user.id],
                "exclude_admins": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["affected_count"] == 1  # Only regular user

        # Verify admin is still active
        test_db.refresh(admin_user)
        test_db.refresh(regular_user)
        assert admin_user.is_active is True
        assert regular_user.is_active is False

    def test_batch_disable_creates_audit_event(
        self, client, admin_auth_override, test_db: Session
    ):
        """Test that batch disable creates a security event."""
        service = UserService(test_db)
        user = service.create_user(email="audit@example.com")

        # Count existing security events
        initial_count = test_db.query(SecurityEvent).count()

        response = client.post(
            "/api/v1/admin/batch/disable-users",
            json={
                "comment": "Audit test: disabling user",
                "user_ids": [user.id],
            },
        )

        assert response.status_code == 200

        # Verify security event was created
        final_count = test_db.query(SecurityEvent).count()
        assert final_count == initial_count + 1

        # Check event details
        event = (
            test_db.query(SecurityEvent)
            .filter(SecurityEvent.event_type == "batch_disable_users")
            .order_by(SecurityEvent.timestamp.desc())
            .first()
        )
        assert event is not None
        assert "Audit test: disabling user" in event.violation_data


class TestBatchDeleteRunners:
    """Tests for POST /api/v1/admin/batch/delete-runners endpoint."""

    def test_batch_delete_runners_requires_comment(self, client, admin_auth_override):
        """Test that batch delete requires a comment."""
        response = client.post(
            "/api/v1/admin/batch/delete-runners",
            json={},
        )
        assert response.status_code == 422

    def test_batch_delete_runners_comment_min_length(self, client, admin_auth_override):
        """Test that comment must be at least 10 characters."""
        response = client.post(
            "/api/v1/admin/batch/delete-runners",
            json={"comment": "short"},
        )
        assert response.status_code == 422

    def test_batch_delete_specific_runners(
        self, client, admin_auth_override, test_db: Session
    ):
        """Test deleting specific runners by ID."""
        # Create test runners
        runner1 = Runner(
            runner_name="batch-runner-1",
            runner_group_id=1,
            labels="[]",
            ephemeral=True,
            provisioned_by="test@example.com",
            status="pending",
            github_url="https://github.com/test-org",
        )
        runner2 = Runner(
            runner_name="batch-runner-2",
            runner_group_id=1,
            labels="[]",
            ephemeral=True,
            provisioned_by="test@example.com",
            status="active",
            github_url="https://github.com/test-org",
        )
        runner3 = Runner(
            runner_name="batch-runner-3",
            runner_group_id=1,
            labels="[]",
            ephemeral=True,
            provisioned_by="other@example.com",
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add_all([runner1, runner2, runner3])
        test_db.commit()
        test_db.refresh(runner1)
        test_db.refresh(runner2)
        test_db.refresh(runner3)

        response = client.post(
            "/api/v1/admin/batch/delete-runners",
            json={
                "comment": "Cleanup: removing test runners",
                "runner_ids": [runner1.id, runner2.id],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "delete_runners"
        assert data["affected_count"] == 2

        # Verify runners are deleted
        test_db.refresh(runner1)
        test_db.refresh(runner2)
        test_db.refresh(runner3)
        assert runner1.status == "deleted"
        assert runner2.status == "deleted"
        assert runner3.status == "active"  # Not in the list

    def test_batch_delete_runners_by_user(
        self, client, admin_auth_override, test_db: Session
    ):
        """Test deleting all runners for a specific user."""
        # Create runners for different users
        runner1 = Runner(
            runner_name="user1-runner-1",
            runner_group_id=1,
            labels="[]",
            ephemeral=True,
            provisioned_by="user1@example.com",
            status="active",
            github_url="https://github.com/test-org",
        )
        runner2 = Runner(
            runner_name="user1-runner-2",
            runner_group_id=1,
            labels="[]",
            ephemeral=True,
            provisioned_by="user1@example.com",
            status="active",
            github_url="https://github.com/test-org",
        )
        runner3 = Runner(
            runner_name="user2-runner-1",
            runner_group_id=1,
            labels="[]",
            ephemeral=True,
            provisioned_by="user2@example.com",
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add_all([runner1, runner2, runner3])
        test_db.commit()
        test_db.refresh(runner1)
        test_db.refresh(runner2)
        test_db.refresh(runner3)

        response = client.post(
            "/api/v1/admin/batch/delete-runners",
            json={
                "comment": "Termination: removing all runners for user1",
                "user_identity": "user1@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["affected_count"] == 2

        # Verify correct runners are deleted
        test_db.refresh(runner1)
        test_db.refresh(runner2)
        test_db.refresh(runner3)
        assert runner1.status == "deleted"
        assert runner2.status == "deleted"
        assert runner3.status == "active"  # Different user

    def test_batch_delete_creates_audit_event(
        self, client, admin_auth_override, test_db: Session
    ):
        """Test that batch delete creates a security event."""
        runner = Runner(
            runner_name="audit-runner",
            runner_group_id=1,
            labels="[]",
            ephemeral=True,
            provisioned_by="test@example.com",
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(runner)
        test_db.commit()
        test_db.refresh(runner)

        # Count existing security events
        initial_count = test_db.query(SecurityEvent).count()

        response = client.post(
            "/api/v1/admin/batch/delete-runners",
            json={
                "comment": "Audit test: deleting runner",
                "runner_ids": [runner.id],
            },
        )

        assert response.status_code == 200

        # Verify security event was created
        final_count = test_db.query(SecurityEvent).count()
        assert final_count == initial_count + 1

        # Check event details
        event = (
            test_db.query(SecurityEvent)
            .filter(SecurityEvent.event_type == "batch_delete_runners")
            .order_by(SecurityEvent.timestamp.desc())
            .first()
        )
        assert event is not None
        assert "Audit test: deleting runner" in event.violation_data

    def test_batch_delete_empty_result(
        self, client, admin_auth_override, test_db: Session
    ):
        """Test batch delete with no matching runners."""
        response = client.post(
            "/api/v1/admin/batch/delete-runners",
            json={
                "comment": "No runners to delete - testing empty case",
                "user_identity": "nonexistent@example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["affected_count"] == 0
