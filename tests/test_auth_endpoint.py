"""Tests for authentication endpoints."""


class TestAuthEndpoint:
    """Test /api/v1/auth/me endpoint."""

    def test_auth_me_endpoint_exists(self, client):
        """Test that /api/v1/auth/me endpoint is accessible."""
        response = client.get("/api/v1/auth/me")
        # Should not return 404
        assert response.status_code != 404

    def test_auth_me_without_token(self, client):
        """Test /api/v1/auth/me without token."""
        response = client.get("/api/v1/auth/me")
        # May be 401/403 (needs auth) or 200 (if OIDC disabled in test)
        assert response.status_code in [200, 401, 403]

    def test_auth_me_response_structure(self, client):
        """Test response structure when accessible."""
        response = client.get("/api/v1/auth/me")
        if response.status_code == 200:
            data = response.json()
            assert "user_id" in data or "error" in data
            if "user_id" in data:
                assert "roles" in data
                assert isinstance(data["roles"], list)
                assert data["roles"][0] in ["admin", "user"]

    def test_auth_me_returns_json(self, client):
        """Test that endpoint returns JSON."""
        response = client.get("/api/v1/auth/me")
        if response.status_code in [200]:
            assert "application/json" in response.headers.get(
                "content-type",
                "",
            )
