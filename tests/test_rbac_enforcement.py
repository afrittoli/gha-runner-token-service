"""Tests for RBAC enforcement across all API endpoints."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.models import Runner
from app.services.user_service import UserService


class TestAdminEndpointsRBAC:
    """Tests that all admin endpoints require admin privileges."""

    ADMIN_ENDPOINTS = [
        # Label policy endpoints
        ("GET", "/api/v1/admin/label-policies"),
        ("POST", "/api/v1/admin/label-policies"),
        ("GET", "/api/v1/admin/label-policies/test@example.com"),
        ("DELETE", "/api/v1/admin/label-policies/test@example.com"),
        # Security events
        ("GET", "/api/v1/admin/security-events"),
        # Sync endpoints
        ("GET", "/api/v1/admin/sync/status"),
        ("POST", "/api/v1/admin/sync/trigger"),
        # User management
        ("GET", "/api/v1/admin/users"),
        ("POST", "/api/v1/admin/users"),
        ("GET", "/api/v1/admin/users/test-uuid"),
        ("PUT", "/api/v1/admin/users/test-uuid"),
        ("DELETE", "/api/v1/admin/users/test-uuid"),
        ("POST", "/api/v1/admin/users/test-uuid/activate"),
        # Batch operations
        ("POST", "/api/v1/admin/batch/disable-users"),
        ("POST", "/api/v1/admin/batch/restore-users"),
        ("POST", "/api/v1/admin/batch/delete-runners"),
    ]

    def test_admin_endpoints_reject_non_admin(
        self, client: TestClient, test_db: Session
    ):
        """Test that all admin endpoints return 403 for non-admin users."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create a non-admin user
        user_service = UserService(test_db)
        db_user = user_service.create_user(email="nonadmin@example.com", is_admin=False)

        # Mock non-admin authenticated user
        non_admin_user = AuthenticatedUser(
            identity="nonadmin@example.com",
            claims={"sub": "auth0|nonadmin", "email": "nonadmin@example.com"},
            db_user=db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = "admin@example.com"  # Non-empty list

        async def override_get_current_user():
            return non_admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            for method, endpoint in self.ADMIN_ENDPOINTS:
                json_body = None
                # Some endpoints require JSON body
                if method == "POST" and "label-policies" in endpoint:
                    json_body = {
                        "user_identity": "test@example.com",
                        "allowed_labels": ["test"],
                    }
                elif (
                    method == "POST"
                    and "users" in endpoint
                    and "activate" not in endpoint
                    and "batch" not in endpoint
                ):
                    json_body = {"email": "new@example.com"}
                elif method == "PUT":
                    json_body = {"display_name": "Test"}
                elif method == "POST" and "batch" in endpoint:
                    json_body = {"comment": "Test batch operation comment"}

                if method == "GET":
                    response = client.get(endpoint)
                elif method == "POST":
                    response = client.post(endpoint, json=json_body)
                elif method == "PUT":
                    response = client.put(endpoint, json=json_body)
                elif method == "DELETE":
                    response = client.delete(endpoint)

                assert response.status_code == 403, (
                    f"Expected 403 for non-admin on {method} {endpoint}, "
                    f"got {response.status_code}"
                )
                detail = response.json().get("detail", "")
                assert "Admin privileges required" in detail
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_admin_endpoints_accept_admin(
        self, client: TestClient, admin_auth_override
    ):
        """Test that admin endpoints accept users with is_admin=True."""
        assert admin_auth_override is not None  # Fixture sets up admin auth
        """Test that admin endpoints accept users with is_admin=True."""
        # Just test a few key endpoints to verify admin access works
        response = client.get("/api/v1/admin/label-policies")
        assert response.status_code == 200

        response = client.get("/api/v1/admin/users")
        assert response.status_code == 200

        response = client.get("/api/v1/admin/security-events")
        assert response.status_code == 200


class TestRunnerEndpointsRBAC:
    """Tests that runner endpoints enforce ownership-based access control."""

    def test_user_can_only_list_own_runners(self, client: TestClient, test_db: Session):
        """Test that users can only see runners they provisioned."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create two users
        user_service = UserService(test_db)
        alice_db = user_service.create_user(email="alice@example.com", can_use_jit=True)
        user_service.create_user(email="bob@example.com", can_use_jit=True)

        # Create runners for each user
        alice_runner = Runner(
            runner_name="alice-runner",
            runner_group_id=1,
            labels='["linux"]',
            ephemeral=True,
            provisioned_by="alice@example.com",
            oidc_sub="auth0|alice",
            status="active",
            github_url="https://github.com/test-org",
        )
        bob_runner = Runner(
            runner_name="bob-runner",
            runner_group_id=1,
            labels='["linux"]',
            ephemeral=True,
            provisioned_by="bob@example.com",
            oidc_sub="auth0|bob",
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add_all([alice_runner, bob_runner])
        test_db.commit()
        test_db.refresh(alice_runner)
        test_db.refresh(bob_runner)

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        # Test as Alice
        alice_user = AuthenticatedUser(
            identity="alice@example.com",
            claims={"sub": "auth0|alice", "email": "alice@example.com"},
            db_user=alice_db,
        )

        async def override_alice():
            return alice_user

        app.dependency_overrides[get_current_user] = override_alice
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.get("/api/v1/runners")
            assert response.status_code == 200
            runners = response.json()["runners"]

            # Alice should only see her runner
            runner_names = [r["runner_name"] for r in runners]
            assert "alice-runner" in runner_names
            assert "bob-runner" not in runner_names
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_user_cannot_view_others_runner(self, client: TestClient, test_db: Session):
        """Test that users cannot view runners owned by others."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create users
        user_service = UserService(test_db)
        alice_db = user_service.create_user(email="alice2@example.com")
        user_service.create_user(email="bob2@example.com")

        # Create runner for Bob
        bob_runner = Runner(
            runner_name="bob-private-runner",
            runner_group_id=1,
            labels='["linux"]',
            ephemeral=True,
            provisioned_by="bob2@example.com",
            oidc_sub="auth0|bob2",
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(bob_runner)
        test_db.commit()
        test_db.refresh(bob_runner)

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        # Alice tries to view Bob's runner
        alice_user = AuthenticatedUser(
            identity="alice2@example.com",
            claims={"sub": "auth0|alice2", "email": "alice2@example.com"},
            db_user=alice_db,
        )

        async def override_alice():
            return alice_user

        app.dependency_overrides[get_current_user] = override_alice
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.get(f"/api/v1/runners/{bob_runner.id}")
            assert response.status_code == 404
            assert "not found or not owned by you" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_user_cannot_delete_others_runner(
        self, client: TestClient, test_db: Session
    ):
        """Test that users cannot delete runners owned by others."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create users
        user_service = UserService(test_db)
        alice_db = user_service.create_user(email="alice3@example.com")
        user_service.create_user(email="bob3@example.com")

        # Create runner for Bob
        bob_runner = Runner(
            runner_name="bob-delete-test",
            runner_group_id=1,
            labels='["linux"]',
            ephemeral=True,
            provisioned_by="bob3@example.com",
            oidc_sub="auth0|bob3",
            status="active",
            github_url="https://github.com/test-org",
        )
        test_db.add(bob_runner)
        test_db.commit()
        test_db.refresh(bob_runner)

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        # Alice tries to delete Bob's runner
        alice_user = AuthenticatedUser(
            identity="alice3@example.com",
            claims={"sub": "auth0|alice3", "email": "alice3@example.com"},
            db_user=alice_db,
        )

        async def override_alice():
            return alice_user

        app.dependency_overrides[get_current_user] = override_alice
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.delete(f"/api/v1/runners/{bob_runner.id}")
            assert response.status_code == 404

            # Verify runner still exists
            test_db.refresh(bob_runner)
            assert bob_runner.status != "deleted"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)


class TestAPIMethodPermissions:
    """Tests for per-method API access control."""

    def test_user_without_jit_access_rejected(
        self, client: TestClient, test_db: Session
    ):
        """Test that users without can_use_jit=True cannot use JIT endpoint."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create user without JIT access
        user_service = UserService(test_db)
        db_user = user_service.create_user(
            email="nojit@example.com",
            can_use_jit=False,
            can_use_registration_token=True,
        )

        mock_user = AuthenticatedUser(
            identity="nojit@example.com",
            claims={"sub": "auth0|nojit", "email": "nojit@example.com"},
            db_user=db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.post(
                "/api/v1/runners/jit",
                json={
                    "runner_name": "test-runner",
                    "labels": ["linux"],
                },
            )
            assert response.status_code == 403
            assert "JIT API not permitted" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_user_without_registration_token_access_rejected(
        self, client: TestClient, test_db: Session
    ):
        """Test users without can_use_registration_token cannot use provision."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create user without registration token access
        user_service = UserService(test_db)
        db_user = user_service.create_user(
            email="noregtoken@example.com",
            can_use_jit=True,
            can_use_registration_token=False,
        )

        mock_user = AuthenticatedUser(
            identity="noregtoken@example.com",
            claims={
                "sub": "auth0|noregtoken",
                "email": "noregtoken@example.com",
            },
            db_user=db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.post(
                "/api/v1/runners/provision",
                json={
                    "runner_name": "test-runner",
                    "labels": ["linux"],
                },
            )
            assert response.status_code == 403
            assert "registration token" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)
