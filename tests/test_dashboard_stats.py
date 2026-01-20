"""Tests for dashboard stats endpoint."""


class TestDashboardStats:
    """Tests for GET /api/v1/dashboard/stats endpoint."""

    def test_stats_endpoint_returns_200(self, client):
        """Test that stats endpoint returns 200 status code."""
        response = client.get("/api/v1/dashboard/stats")
        assert response.status_code == 200

    def test_stats_response_structure(self, client):
        """Test that stats response has required fields."""
        response = client.get("/api/v1/dashboard/stats")
        data = response.json()

        assert "total" in data
        assert "active" in data
        assert "offline" in data
        assert "pending" in data
        assert "recent_events" in data

    def test_stats_response_types(self, client):
        """Test that stats response has correct types."""
        response = client.get("/api/v1/dashboard/stats")
        data = response.json()

        assert isinstance(data["total"], int)
        assert isinstance(data["active"], int)
        assert isinstance(data["offline"], int)
        assert isinstance(data["pending"], int)
        assert isinstance(data["recent_events"], list)

    def test_stats_counts_are_non_negative(self, client):
        """Test that all counts are non-negative."""
        response = client.get("/api/v1/dashboard/stats")
        data = response.json()

        assert data["total"] >= 0
        assert data["active"] >= 0
        assert data["offline"] >= 0
        assert data["pending"] >= 0

    def test_stats_event_structure(self, client):
        """Test that recent events have correct structure."""
        response = client.get("/api/v1/dashboard/stats")
        data = response.json()

        # If there are events, check their structure
        if data["recent_events"]:
            event = data["recent_events"][0]
            assert "timestamp" in event
            assert "event_type" in event
            assert "severity" in event
            assert "description" in event
            assert isinstance(event["timestamp"], str)
            assert isinstance(event["event_type"], str)
            assert isinstance(event["severity"], str)
            assert isinstance(event["description"], str)
