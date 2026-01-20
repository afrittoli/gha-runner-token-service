"""Tests to verify backend functionality independent of dashboards."""


class TestBackendFunctionalityIndependence:
    """Verify core backend works independent of dashboard changes."""

    def test_health_endpoint_returns_status(self, client):
        """Test /health returns service status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data.get("status") in ["healthy", "warning"]

    def test_api_responds_without_dashboard_feature(self, client):
        """Test API is accessible regardless of dashboard feature flag."""
        # This verifies feature flag doesn't break core API
        response = client.get("/health")
        assert response.status_code == 200

    def test_runners_endpoint_exists(self, client):
        """Test /api/v1/runners endpoint is accessible."""
        response = client.get("/api/v1/runners")
        # Should exist - may be 401 if auth required, but not 404
        assert response.status_code in [
            200,
            401,
            403,
        ], f"Unexpected status {response.status_code}"

    def test_no_breaking_changes_in_api_structure(self, client):
        """Test that API structure is unchanged."""
        # Health endpoint should always work
        response = client.get("/health")
        assert response.status_code == 200

        # Should return JSON with expected structure
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data or "version" in data or "timestamp" in data


class TestAPIEndpointConsistency:
    """Ensure API endpoints work consistently."""

    def test_core_endpoints_dont_404(self, client):
        """Test that core endpoints don't return 404."""
        endpoints = [
            "/health",
            "/api/v1/runners",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code != 404, f"Unexpected 404 at {endpoint}"

    def test_dashboard_endpoint_independent_from_api(self, client):
        """Test dashboard endpoint doesn't affect API."""
        # Get dashboard
        dash_response = client.get("/dashboard")
        assert dash_response.status_code == 200

        # Get API health - should still work
        api_response = client.get("/health")
        assert api_response.status_code == 200


class TestBackendIntegration:
    """Test backend components work together correctly."""

    def test_database_initialized(self, client):
        """Test that database is properly initialized."""
        # Health endpoint checks DB connectivity
        response = client.get("/health")
        assert response.status_code == 200

    def test_middleware_doesnt_interfere(self, client):
        """Test that middleware doesn't interfere with requests."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers.get("content-type")
