"""Tests for API endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert data["service"] == "GitHub Runner Token Service"
    assert "version" in data


def test_provision_runner_no_auth():
    """Test provisioning without authentication."""
    response = client.post(
        "/api/v1/runners/provision",
        json={"runner_name": "test-runner", "labels": ["test"]},
    )

    # Should require authentication
    assert response.status_code in [401, 403]


def test_list_runners_no_auth():
    """Test listing runners without authentication."""
    response = client.get("/api/v1/runners")

    # Should require authentication
    assert response.status_code in [401, 403]
