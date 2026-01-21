"""Tests for enhanced runners endpoint with filtering."""


class TestEnhancedRunnersEndpoint:
    """Tests for GET /api/v1/runners with query parameters."""

    def test_list_runners_endpoint_exists(self, client):
        """Test that list runners endpoint is accessible."""
        # Without authentication, should get 401
        response = client.get("/api/v1/runners")
        assert response.status_code == 401

    def test_list_runners_pagination_parameters(self, client):
        """Test that pagination parameters are accepted."""
        # This is a schema test - verify parameters are documented
        # In a real test, we'd have an authenticated client

        # Test parameter parsing with a mock scenario
        # The endpoint should accept: limit, offset, status, ephemeral
        response_doc = client.get("/openapi.json")
        assert response_doc.status_code == 200

        openapi_spec = response_doc.json()
        runners_endpoint = openapi_spec["paths"]["/api/v1/runners"]["get"]

        # Verify parameters exist in OpenAPI spec
        parameters = runners_endpoint.get("parameters", [])
        param_names = [p["name"] for p in parameters]

        assert "limit" in param_names
        assert "offset" in param_names
        assert "status" in param_names
        assert "ephemeral" in param_names

    def test_endpoint_backward_compatibility(self, client):
        """Test that endpoint without parameters still works."""
        # The endpoint should work whether or not query params are provided
        # Without auth, we expect 401, which means auth is checked first
        response_no_params = client.get("/api/v1/runners")
        response_with_params = client.get("/api/v1/runners?limit=10&offset=0")

        # Both should return same status (both 401 - auth required)
        assert response_no_params.status_code == response_with_params.status_code
