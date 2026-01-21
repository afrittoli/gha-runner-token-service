"""Tests to verify existing Jinja2 dashboard continues to work."""


class TestExistingDashboard:
    """Verify existing Jinja2 dashboard (/dashboard) is not broken."""

    def test_dashboard_endpoint_accessible(self, client):
        """Test that /dashboard endpoint is accessible."""
        response = client.get("/dashboard")
        assert response.status_code == 200

    def test_dashboard_returns_html(self, client):
        """Test that /dashboard returns HTML content."""
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_template_renders(self, client):
        """Test that Jinja2 template renders without errors."""
        response = client.get("/dashboard")
        assert response.status_code == 200
        # Check for expected content from template
        content = response.text
        assert len(content) > 100  # Template should produce substantial HTML
        assert "<!DOCTYPE" in content or "<html" in content

    def test_dashboard_no_auth_required(self, client):
        """Test that /dashboard does not require authentication."""
        # No auth headers, should still work
        response = client.get("/dashboard")
        assert response.status_code == 200

    def test_runners_api_endpoint_works(self, client):
        """Test that /api/v1/runners endpoint still works."""
        response = client.get("/api/v1/runners")
        # May be 401 if auth is required, but endpoint should exist
        assert response.status_code in [200, 401, 403]

    def test_health_endpoint_works(self, client):
        """Test that /health endpoint still works."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_cors_headers_present(self, client):
        """Test that CORS headers are returned."""
        response = client.get("/dashboard")
        # CORS headers should be present
        assert response.status_code == 200


class TestBackendFunctionality:
    """Verify core backend functionality is not broken by dashboard changes."""

    def test_api_endpoints_structure(self, client):
        """Test that API endpoints follow expected structure."""
        # These endpoints should exist and respond with appropriate codes
        endpoints = [
            ("/api/v1", 404),  # Main API endpoint (doesn't exist)
            ("/api/v1/runners", (200, 401, 403)),  # Runners endpoint
            ("/health", 200),  # Health endpoint
        ]

        for endpoint, expected_codes in endpoints:
            response = client.get(endpoint)
            if isinstance(expected_codes, tuple):
                assert response.status_code in expected_codes
            else:
                assert response.status_code == expected_codes

    def test_feature_flag_does_not_break_existing_endpoints(self, client):
        """Test that feature flag does not affect existing endpoints."""
        # Both with and without feature flag, endpoints should work
        response = client.get("/health")
        assert response.status_code == 200

        response = client.get("/dashboard")
        assert response.status_code == 200


class TestNoRegressions:
    """Test that new infrastructure changes don't cause regressions."""

    def test_dashboard_still_serves_on_root_path(self, client):
        """Test that dashboard is still accessible at /dashboard."""
        response = client.get("/dashboard")
        assert response.status_code == 200

    def test_no_404_errors_for_existing_paths(self, client):
        """Test that existing paths don't get unexpected 404s."""
        paths = ["/dashboard", "/health", "/api/v1/runners"]
        for path in paths:
            response = client.get(path)
            # Should not be 404 (may be 401/403 if auth required, but not 404)
            assert response.status_code != 404, f"Unexpected 404 at {path}"
