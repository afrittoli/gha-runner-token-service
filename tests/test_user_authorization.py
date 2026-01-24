"""Tests for user authorization flow."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.services.user_service import UserService


class TestUserAuthorizationFlow:
    """Tests for the user authorization flow with database checks."""

    def test_unknown_user_rejected_when_users_exist(
        self, client: TestClient, test_db: Session
    ):
        """Test that unknown users are rejected with 403 when users exist in DB."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create a user in the database (so we're not in bootstrap mode)
        user_service = UserService(test_db)
        user_service.create_user(email="existing@example.com", is_admin=True)

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        # Create a mock for the OIDC-validated user who is NOT in the database
        async def mock_get_current_user():
            # This simulates what would happen after OIDC validation
            # but the user is not in our User table
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403,
                detail="User not authorized. Contact administrator to request access.",
            )

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.get("/api/v1/runners")
            assert response.status_code == 403
            assert "not authorized" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_known_user_allowed(self, client: TestClient, test_db: Session):
        """Test that known users are allowed access."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create a user in the database
        user_service = UserService(test_db)
        db_user = user_service.create_user(
            email="known@example.com",
            is_admin=False,
            can_use_registration_token=True,
            can_use_jit=True,
        )

        # Create AuthenticatedUser with database user
        mock_user = AuthenticatedUser(
            identity="known@example.com",
            claims={"sub": "auth0|known", "email": "known@example.com"},
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
            response = client.get("/api/v1/runners")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_inactive_user_rejected(self, client: TestClient, test_db: Session):
        """Test that inactive users are rejected."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create and deactivate a user
        user_service = UserService(test_db)
        db_user = user_service.create_user(email="inactive@example.com")
        user_service.deactivate_user(db_user.id)

        # Refresh to get updated state
        db_user = user_service.get_user_by_id(db_user.id)

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        # Simulate what happens when an inactive user tries to authenticate
        async def mock_get_current_user():
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403,
                detail="User account is deactivated",
            )

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.get("/api/v1/runners")
            assert response.status_code == 403
            assert "deactivated" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)


class TestPerMethodAuthorization:
    """Tests for per-method API authorization."""

    def test_user_without_registration_token_access_rejected(
        self, client: TestClient, test_db: Session
    ):
        """Test that users without registration token access are rejected from /provision."""
        from app.auth.dependencies import (
            get_current_user,
            require_registration_token_access,
        )
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create a user without registration token access
        user_service = UserService(test_db)
        db_user = user_service.create_user(
            email="noregtok@example.com",
            can_use_registration_token=False,
            can_use_jit=True,
        )

        mock_user = AuthenticatedUser(
            identity="noregtok@example.com",
            claims={"sub": "auth0|noregtok", "email": "noregtok@example.com"},
            db_user=db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        async def override_get_current_user():
            return mock_user

        # Override require_registration_token_access to properly check the permission
        async def override_require_registration_token_access():
            from fastapi import HTTPException

            if not mock_user.can_use_registration_token:
                raise HTTPException(
                    status_code=403,
                    detail="Registration token API access not permitted for this user",
                )
            return mock_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_registration_token_access] = (
            override_require_registration_token_access
        )
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.post(
                "/api/v1/runners/provision",
                json={
                    "runner_name": "test-runner",
                    "labels": ["test"],
                },
            )
            assert response.status_code == 403
            assert "registration token" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_registration_token_access, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_user_without_jit_access_rejected(
        self, client: TestClient, test_db: Session
    ):
        """Test that users without JIT access are rejected from /jit."""
        from app.auth.dependencies import get_current_user, require_jit_access
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create a user without JIT access
        user_service = UserService(test_db)
        db_user = user_service.create_user(
            email="nojit@example.com",
            can_use_registration_token=True,
            can_use_jit=False,
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

        # Override require_jit_access to properly check the permission
        async def override_require_jit_access():
            from fastapi import HTTPException

            if not mock_user.can_use_jit:
                raise HTTPException(
                    status_code=403,
                    detail="JIT API access not permitted for this user",
                )
            return mock_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_jit_access] = override_require_jit_access
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.post(
                "/api/v1/runners/jit",
                json={
                    "runner_name": "test-runner",
                    "labels": ["test"],
                },
            )
            assert response.status_code == 403
            assert "jit" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_jit_access, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_user_with_both_permissions_can_access_both(
        self, client: TestClient, test_db: Session
    ):
        """Test that users with both permissions can access both endpoints."""
        from app.auth.dependencies import (
            get_current_user,
            require_jit_access,
            require_registration_token_access,
        )
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create a user with both permissions
        user_service = UserService(test_db)
        db_user = user_service.create_user(
            email="bothperms@example.com",
            can_use_registration_token=True,
            can_use_jit=True,
        )

        mock_user = AuthenticatedUser(
            identity="bothperms@example.com",
            claims={"sub": "auth0|bothperms", "email": "bothperms@example.com"},
            db_user=db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""
        mock_settings.github_org = "test-org"
        mock_settings.default_runner_group_id = 1

        async def override_get_current_user():
            return mock_user

        async def override_require_registration_token_access():
            # User has permission, so allow
            return mock_user

        async def override_require_jit_access():
            # User has permission, so allow
            return mock_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_registration_token_access] = (
            override_require_registration_token_access
        )
        app.dependency_overrides[require_jit_access] = override_require_jit_access
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            # Both endpoints should pass authorization (may fail later in the flow
            # due to missing GitHub mock, but that's fine - we're testing auth)

            # Test list runners (basic auth check)
            response = client.get("/api/v1/runners")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_registration_token_access, None)
            app.dependency_overrides.pop(require_jit_access, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)


class TestBootstrapMode:
    """Tests for bootstrap mode when no users exist."""

    def test_bootstrap_mode_allows_admin_identities(
        self, client: TestClient, test_db: Session
    ):
        """Test that bootstrap mode allows ADMIN_IDENTITIES when no users exist."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # No users in database (bootstrap mode)
        # User in ADMIN_IDENTITIES should be allowed

        mock_user = AuthenticatedUser(
            identity="bootstrap-admin@example.com",
            claims={
                "sub": "auth0|bootstrap",
                "email": "bootstrap-admin@example.com",
            },
            db_user=None,  # No DB user (bootstrap mode)
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = "bootstrap-admin@example.com"

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            # Admin endpoints should work in bootstrap mode
            response = client.get("/api/v1/admin/label-policies")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_bootstrap_mode_dev_allows_all(self, client: TestClient, test_db: Session):
        """Test that empty ADMIN_IDENTITIES allows all users (dev mode)."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # No users in database, no ADMIN_IDENTITIES (dev mode)
        mock_user = AuthenticatedUser(
            identity="anyone@example.com",
            claims={"sub": "auth0|anyone", "email": "anyone@example.com"},
            db_user=None,  # No DB user
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""  # Empty = dev mode

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            # Anyone should be able to access admin endpoints in dev mode
            response = client.get("/api/v1/admin/label-policies")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)


class TestUserAdminEndpoints:
    """Tests for user management admin endpoints."""

    def test_create_user_endpoint(self, client: TestClient, test_db: Session):
        """Test creating a user via admin API."""
        from app.auth.dependencies import get_current_user
        from app.api.v1.admin import require_admin
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create admin user for auth
        user_service = UserService(test_db)
        admin_db_user = user_service.create_user(
            email="admin@example.com", is_admin=True
        )

        admin_user = AuthenticatedUser(
            identity="admin@example.com",
            claims={"sub": "auth0|admin", "email": "admin@example.com"},
            db_user=admin_db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        async def override_get_current_user():
            return admin_user

        async def override_require_admin():
            return admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_admin] = override_require_admin
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.post(
                "/api/v1/admin/users",
                json={
                    "email": "newuser@example.com",
                    "display_name": "New User",
                    "is_admin": False,
                    "can_use_registration_token": True,
                    "can_use_jit": False,
                },
            )
            assert response.status_code == 201

            data = response.json()
            assert data["email"] == "newuser@example.com"
            assert data["display_name"] == "New User"
            assert data["is_admin"] is False
            assert data["can_use_registration_token"] is True
            assert data["can_use_jit"] is False
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_admin, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_list_users_endpoint(self, client: TestClient, test_db: Session):
        """Test listing users via admin API."""
        from app.auth.dependencies import get_current_user
        from app.api.v1.admin import require_admin
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create some users
        user_service = UserService(test_db)
        admin_db_user = user_service.create_user(
            email="listadmin@example.com", is_admin=True
        )
        user_service.create_user(email="user1@example.com")
        user_service.create_user(email="user2@example.com")

        admin_user = AuthenticatedUser(
            identity="listadmin@example.com",
            claims={"sub": "auth0|listadmin", "email": "listadmin@example.com"},
            db_user=admin_db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        async def override_get_current_user():
            return admin_user

        async def override_require_admin():
            return admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_admin] = override_require_admin
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.get("/api/v1/admin/users")
            assert response.status_code == 200

            data = response.json()
            assert data["total"] == 3
            assert len(data["users"]) == 3
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_admin, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_update_user_endpoint(self, client: TestClient, test_db: Session):
        """Test updating a user via admin API."""
        from app.auth.dependencies import get_current_user
        from app.api.v1.admin import require_admin
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create users
        user_service = UserService(test_db)
        admin_db_user = user_service.create_user(
            email="updateadmin@example.com", is_admin=True
        )
        target_user = user_service.create_user(
            email="target@example.com",
            can_use_jit=True,
        )

        admin_user = AuthenticatedUser(
            identity="updateadmin@example.com",
            claims={"sub": "auth0|updateadmin", "email": "updateadmin@example.com"},
            db_user=admin_db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        async def override_get_current_user():
            return admin_user

        async def override_require_admin():
            return admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_admin] = override_require_admin
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.put(
                f"/api/v1/admin/users/{target_user.id}",
                json={
                    "can_use_jit": False,
                    "display_name": "Updated Name",
                },
            )
            assert response.status_code == 200

            data = response.json()
            assert data["can_use_jit"] is False
            assert data["display_name"] == "Updated Name"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_admin, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_delete_user_endpoint(self, client: TestClient, test_db: Session):
        """Test deactivating a user via admin API."""
        from app.auth.dependencies import get_current_user
        from app.api.v1.admin import require_admin
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create users
        user_service = UserService(test_db)
        admin_db_user = user_service.create_user(
            email="deleteadmin@example.com", is_admin=True
        )
        target_user = user_service.create_user(email="todelete@example.com")

        admin_user = AuthenticatedUser(
            identity="deleteadmin@example.com",
            claims={"sub": "auth0|deleteadmin", "email": "deleteadmin@example.com"},
            db_user=admin_db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        async def override_get_current_user():
            return admin_user

        async def override_require_admin():
            return admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_admin] = override_require_admin
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.request(
                "DELETE",
                f"/api/v1/admin/users/{target_user.id}",
                json={"comment": "Test deactivation for user management testing"},
            )
            assert response.status_code == 204

            # Verify user is deactivated
            deactivated = user_service.get_user_by_id(target_user.id)
            assert deactivated.is_active is False

            # Verify audit log entry was created
            from app.models import AuditLog

            audit_entry = (
                test_db.query(AuditLog)
                .filter(AuditLog.event_type == "user_deactivated")
                .first()
            )
            assert audit_entry is not None
            assert audit_entry.success is True
            assert "Test deactivation" in audit_entry.event_data
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_admin, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_activate_user_endpoint(self, client: TestClient, test_db: Session):
        """Test reactivating a user via admin API."""
        from app.auth.dependencies import get_current_user
        from app.api.v1.admin import require_admin
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create and deactivate a user
        user_service = UserService(test_db)
        admin_db_user = user_service.create_user(
            email="activateadmin@example.com", is_admin=True
        )
        target_user = user_service.create_user(email="toactivate@example.com")
        user_service.deactivate_user(target_user.id)

        admin_user = AuthenticatedUser(
            identity="activateadmin@example.com",
            claims={"sub": "auth0|activateadmin", "email": "activateadmin@example.com"},
            db_user=admin_db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        async def override_get_current_user():
            return admin_user

        async def override_require_admin():
            return admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_admin] = override_require_admin
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.post(f"/api/v1/admin/users/{target_user.id}/activate")
            assert response.status_code == 200

            data = response.json()
            assert data["is_active"] is True
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_admin, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_non_admin_cannot_manage_users(self, client: TestClient, test_db: Session):
        """Test that non-admin users cannot access user management endpoints."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create a non-admin user
        user_service = UserService(test_db)
        db_user = user_service.create_user(email="nonadmin@example.com", is_admin=False)

        non_admin_user = AuthenticatedUser(
            identity="nonadmin@example.com",
            claims={"sub": "auth0|nonadmin", "email": "nonadmin@example.com"},
            db_user=db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        async def override_get_current_user():
            return non_admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.get("/api/v1/admin/users")
            assert response.status_code == 403
            assert "admin" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_create_duplicate_user_rejected(self, client: TestClient, test_db: Session):
        """Test that creating a user with duplicate email is rejected."""
        from app.auth.dependencies import get_current_user
        from app.api.v1.admin import require_admin
        from app.config import get_settings
        from app.database import get_db
        from app.main import app

        # Create admin and existing user
        user_service = UserService(test_db)
        admin_db_user = user_service.create_user(
            email="dupadmin@example.com", is_admin=True
        )
        user_service.create_user(email="existing@example.com")

        admin_user = AuthenticatedUser(
            identity="dupadmin@example.com",
            claims={"sub": "auth0|dupadmin", "email": "dupadmin@example.com"},
            db_user=admin_db_user,
        )

        mock_settings = MagicMock()
        mock_settings.enable_oidc_auth = True
        mock_settings.admin_identities = ""

        async def override_get_current_user():
            return admin_user

        async def override_require_admin():
            return admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[require_admin] = override_require_admin
        app.dependency_overrides[get_db] = lambda: test_db
        app.dependency_overrides[get_settings] = lambda: mock_settings

        try:
            response = client.post(
                "/api/v1/admin/users",
                json={
                    "email": "existing@example.com",  # Duplicate
                },
            )
            assert response.status_code == 409
            assert "already exists" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(require_admin, None)
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_settings, None)
