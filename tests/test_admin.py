"""Tests for admin API endpoints and admin role checking."""

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.dependencies import AuthenticatedUser
from app.models import SecurityEvent


class TestAdminRoleChecking:
    """Tests for admin role checking functionality."""

    def test_admin_access_denied_for_non_admin(
        self, client: TestClient, test_db: Session, mock_user: AuthenticatedUser
    ):
        """Test that non-admin users are denied access to admin endpoints."""
        from app.auth.dependencies import get_current_user
        from app.main import app

        async def override_get_current_user():
            return mock_user  # mock_user has is_admin=False

        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            response = client.get("/api/v1/admin/security-events")
            assert response.status_code == 403
            assert "Admin privileges required" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_admin_access_granted_for_db_admin(
        self, client: TestClient, test_db: Session
    ):
        """Test that users with is_admin=True in the DB have admin access."""
        from app.auth.dependencies import get_current_user
        from app.main import app
        from app.models import User

        db_user = User(
            email="admin@example.com",
            is_admin=True,
            is_active=True,
            can_use_jit=True,
        )
        admin_user = AuthenticatedUser(
            identity="admin@example.com",
            claims={"sub": "auth0|admin123", "email": "admin@example.com"},
            db_user=db_user,
        )

        async def override_get_current_user():
            return admin_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            response = client.get("/api/v1/admin/security-events")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)


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
            user_id="m2m:test-team",
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
                user_id="m2m:test-team",
                violation_data=json.dumps({}),
            )
            test_db.add(event)
        test_db.commit()

        response = client.get("/api/v1/admin/security-events?severity=high")
        assert response.status_code == 200

        data = response.json()
        for event in data["events"]:
            assert event["severity"] == "high"
