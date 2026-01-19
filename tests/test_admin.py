"""Tests for admin API endpoints and admin role checking."""

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.models import LabelPolicy, SecurityEvent


class TestAdminRoleChecking:
    """Tests for admin role checking functionality."""

    def test_admin_access_with_empty_admin_list(
        self, client: TestClient, test_db: Session, mock_user: AuthenticatedUser
    ):
        """Test that all authenticated users have admin access when ADMIN_IDENTITIES is empty (dev mode)."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.main import app
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.admin_identities = ""  # Empty = dev mode

        async def override_get_current_user():
            return mock_user

        def override_get_settings():
            return mock_settings

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_settings] = override_get_settings

        try:
            response = client.get("/api/v1/admin/label-policies")
            # Should succeed because empty admin list means all users are admins
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_admin_access_denied_for_non_admin(
        self, client: TestClient, test_db: Session, mock_user: AuthenticatedUser
    ):
        """Test that non-admin users are denied access when ADMIN_IDENTITIES is configured."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.main import app
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.admin_identities = "admin@example.com,other-admin@example.com"

        async def override_get_current_user():
            return mock_user  # test-user@example.com is NOT in admin list

        def override_get_settings():
            return mock_settings

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_settings] = override_get_settings

        try:
            response = client.get("/api/v1/admin/label-policies")
            assert response.status_code == 403
            assert "Admin privileges required" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_admin_access_granted_by_identity(
        self, client: TestClient, test_db: Session
    ):
        """Test that users in ADMIN_IDENTITIES list have admin access (by email)."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.main import app
        from unittest.mock import MagicMock

        admin_user = AuthenticatedUser(
            identity="admin@example.com",
            claims={"sub": "auth0|admin123", "email": "admin@example.com"},
        )

        mock_settings = MagicMock()
        mock_settings.admin_identities = "admin@example.com"

        async def override_get_current_user():
            return admin_user

        def override_get_settings():
            return mock_settings

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_settings] = override_get_settings

        try:
            response = client.get("/api/v1/admin/label-policies")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_settings, None)

    def test_admin_access_granted_by_sub(self, client: TestClient, test_db: Session):
        """Test that users in ADMIN_IDENTITIES list have admin access (by OIDC sub)."""
        from app.auth.dependencies import get_current_user
        from app.config import get_settings
        from app.main import app
        from unittest.mock import MagicMock

        admin_user = AuthenticatedUser(
            identity="some-other-identity",  # Identity doesn't match
            claims={"sub": "auth0|admin123", "email": "admin@example.com"},
        )

        mock_settings = MagicMock()
        mock_settings.admin_identities = "auth0|admin123"  # But sub matches

        async def override_get_current_user():
            return admin_user

        def override_get_settings():
            return mock_settings

        app.dependency_overrides[get_current_user] = override_get_current_user
        app.dependency_overrides[get_settings] = override_get_settings

        try:
            response = client.get("/api/v1/admin/label-policies")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_settings, None)


class TestLabelPolicyEndpoints:
    """Tests for label policy management endpoints."""

    def test_create_label_policy(
        self, client: TestClient, test_db: Session, admin_auth_override
    ):
        """Test creating a label policy."""
        policy_data = {
            "user_identity": "user@example.com",
            "allowed_labels": ["team-a", "linux", "docker"],
            "label_patterns": ["team-a-.*"],
            "max_runners": 10,
            "description": "Test policy",
        }

        response = client.post("/api/v1/admin/label-policies", json=policy_data)
        assert response.status_code == 201

        data = response.json()
        assert data["user_identity"] == "user@example.com"
        assert data["allowed_labels"] == ["team-a", "linux", "docker"]
        assert data["max_runners"] == 10

    def test_list_label_policies(
        self, client: TestClient, test_db: Session, admin_auth_override
    ):
        """Test listing label policies."""
        # Create a policy first
        policy = LabelPolicy(
            user_identity="user1@example.com",
            allowed_labels=json.dumps(["label1", "label2"]),
            max_runners=5,
        )
        test_db.add(policy)
        test_db.commit()

        response = client.get("/api/v1/admin/label-policies")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] >= 1
        assert len(data["policies"]) >= 1

    def test_get_label_policy(
        self, client: TestClient, test_db: Session, admin_auth_override
    ):
        """Test getting a specific label policy."""
        # Create a policy first
        policy = LabelPolicy(
            user_identity="specific-user@example.com",
            allowed_labels=json.dumps(["specific-label"]),
            max_runners=3,
        )
        test_db.add(policy)
        test_db.commit()

        response = client.get("/api/v1/admin/label-policies/specific-user@example.com")
        assert response.status_code == 200

        data = response.json()
        assert data["user_identity"] == "specific-user@example.com"
        assert data["allowed_labels"] == ["specific-label"]

    def test_get_label_policy_not_found(
        self, client: TestClient, test_db: Session, admin_auth_override
    ):
        """Test getting a non-existent label policy."""
        response = client.get("/api/v1/admin/label-policies/nonexistent@example.com")
        assert response.status_code == 404

    def test_delete_label_policy(
        self, client: TestClient, test_db: Session, admin_auth_override
    ):
        """Test deleting a label policy."""
        # Create a policy first
        policy = LabelPolicy(
            user_identity="delete-me@example.com",
            allowed_labels=json.dumps(["label"]),
        )
        test_db.add(policy)
        test_db.commit()

        response = client.delete("/api/v1/admin/label-policies/delete-me@example.com")
        assert response.status_code == 204

        # Verify it's deleted
        response = client.get("/api/v1/admin/label-policies/delete-me@example.com")
        assert response.status_code == 404


class TestSecurityEventsEndpoints:
    """Tests for security events endpoints."""

    def test_list_security_events(
        self, client: TestClient, test_db: Session, admin_auth_override
    ):
        """Test listing security events."""
        # Create a security event
        event = SecurityEvent(
            event_type="label_policy_violation",
            severity="medium",
            user_identity="violator@example.com",
            violation_data=json.dumps({"reason": "test violation"}),
        )
        test_db.add(event)
        test_db.commit()

        response = client.get("/api/v1/admin/security-events")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] >= 1

    def test_filter_security_events_by_severity(
        self, client: TestClient, test_db: Session, admin_auth_override
    ):
        """Test filtering security events by severity."""
        # Create events with different severities
        for severity in ["low", "medium", "high"]:
            event = SecurityEvent(
                event_type="test_event",
                severity=severity,
                user_identity="test@example.com",
                violation_data=json.dumps({}),
            )
            test_db.add(event)
        test_db.commit()

        response = client.get("/api/v1/admin/security-events?severity=high")
        assert response.status_code == 200

        data = response.json()
        for event in data["events"]:
            assert event["severity"] == "high"
