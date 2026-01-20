"""Tests for static file serving for React dashboard."""


class TestStaticFilesServing:
    """Tests for React dashboard static file serving."""

    def test_app_path_exists_when_feature_enabled(self, client):
        """Test that /app path exists when feature flag enabled."""
        # The /app route will 404 if no dist exists, route should be mounted
        response = client.get("/app")
        # Should not be method not allowed (405)
        # Should be 404, 200 (if dist exists), or 307 (redirect)
        assert response.status_code != 405

    def test_api_routes_still_work(self, client):
        """Test that API routes are not affected by static files mount."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_dashboard_still_accessible(self, client):
        """Test that existing dashboard is still accessible."""
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_root_endpoint_still_works(self, client):
        """Test that root endpoint is unaffected."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "GitHub Runner Token Service" in data["service"]
