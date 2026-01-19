"""Tests for basic API endpoints (health, root, docs)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Tests for health and status endpoints."""

    def test_health_check(self):
        """Test health check endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_root_endpoint(self):
        """Test root endpoint returns service info."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "GitHub Runner Token Service"
        assert "version" in data


class TestDocumentation:
    """Tests for API documentation endpoints."""

    def test_openapi_schema_available(self):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data

    def test_swagger_ui_available(self):
        """Test that Swagger UI is available."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    def test_redoc_available(self):
        """Test that ReDoc is available."""
        response = client.get("/redoc")
        assert response.status_code == 200


class TestAuthenticationRequired:
    """Tests verifying authentication is required for protected endpoints."""

    def test_provision_runner_no_auth(self):
        """Test provisioning without authentication fails."""
        response = client.post(
            "/api/v1/runners/provision",
            json={"runner_name": "test-runner", "labels": ["test"]},
        )
        # Should require authentication
        assert response.status_code in [401, 403]

    def test_list_runners_no_auth(self):
        """Test listing runners without authentication fails."""
        response = client.get("/api/v1/runners")
        # Should require authentication
        assert response.status_code in [401, 403]

    def test_admin_endpoints_no_auth(self):
        """Test admin endpoints without authentication fail."""
        response = client.get("/api/v1/admin/label-policies")
        assert response.status_code in [401, 403]

        response = client.get("/api/v1/admin/security-events")
        assert response.status_code in [401, 403]


class TestDashboard:
    """Tests for dashboard endpoint."""

    def test_dashboard_accessible(self):
        """Test that dashboard is accessible without authentication."""
        response = client.get("/dashboard")
        assert response.status_code == 200
        # Should return HTML
        assert "text/html" in response.headers.get("content-type", "")
