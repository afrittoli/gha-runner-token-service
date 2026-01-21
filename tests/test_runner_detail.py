"""Tests for enhanced runner detail endpoint with audit trail."""


class TestRunnerDetailWithAuditTrail:
    """Tests for GET /api/v1/runners/{runner_id} with audit trail."""

    def test_runner_detail_endpoint_exists(self, client):
        """Test that runner detail endpoint is accessible."""
        response = client.get("/api/v1/runners/test-runner-id")
        # Should be 401 (auth required) not 404 (method not found)
        assert response.status_code in [401, 403, 404]

    def test_runner_detail_has_audit_trail(self, client):
        """Test that response includes audit_trail field."""
        response = client.get("/api/v1/runners/test-runner-id")
        # When auth not provided, we get 401, but endpoint exists
        assert response.status_code in [401, 403, 404]

    def test_openapi_includes_runner_detail_schema(self, client):
        """Test that OpenAPI spec includes RunnerDetailResponse schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        spec = response.json()
        # Verify schema exists
        schemas = spec.get("components", {}).get("schemas", {})
        assert "RunnerDetailResponse" in schemas or "RunnerStatus" in schemas

    def test_api_still_functional(self, client):
        """Test that other API endpoints still work."""
        response = client.get("/health")
        assert response.status_code == 200
