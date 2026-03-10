"""Tests for sync status API endpoint reading from database."""

import json
from datetime import datetime, timezone

from app.main import get_sync_status
from app.models import SyncState


def test_get_sync_status_with_data(test_db):
    """Test get_sync_status returns data from sync_state table."""
    # Create sync state
    sync_result = {"updated": 5, "deleted": 2, "unchanged": 10}
    sync_state = SyncState(
        id=1,
        worker_hostname="worker-pod-1",
        worker_heartbeat=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        last_sync_time=datetime(2024, 1, 15, 10, 29, 55, tzinfo=timezone.utc),
        last_sync_result=json.dumps(sync_result),
        last_sync_error=None,
    )
    test_db.add(sync_state)
    test_db.commit()

    # Get status
    status = get_sync_status(test_db)

    # Verify
    assert "enabled" in status  # Config value (now defaults to False)
    assert status["worker_hostname"] == "worker-pod-1"
    # SQLite strips timezone info, so just check the date/time part
    assert status["worker_heartbeat"].startswith("2024-01-15T10:30:00")
    assert status["last_sync_time"].startswith("2024-01-15T10:29:55")
    assert status["last_sync_result"] == sync_result
    assert status["last_sync_error"] is None


def test_get_sync_status_with_error(test_db):
    """Test get_sync_status returns error from sync_state table."""
    sync_state = SyncState(
        id=1,
        worker_hostname="worker-pod-2",
        worker_heartbeat=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        last_sync_time=None,
        last_sync_result=None,
        last_sync_error="GitHub API rate limit exceeded",
    )
    test_db.add(sync_state)
    test_db.commit()

    status = get_sync_status(test_db)

    assert status["worker_hostname"] == "worker-pod-2"
    assert status["last_sync_time"] is None
    assert status["last_sync_result"] is None
    assert status["last_sync_error"] == "GitHub API rate limit exceeded"


def test_get_sync_status_no_worker(test_db):
    """Test get_sync_status when no worker has started yet."""
    # No sync_state record exists
    status = get_sync_status(test_db)

    assert "enabled" in status  # Config value
    assert (
        status["last_sync_error"] == "Sync worker not initialized (requires PostgreSQL)"
    )


def test_get_sync_status_invalid_json(test_db):
    """Test get_sync_status handles invalid JSON in last_sync_result."""
    sync_state = SyncState(
        id=1,
        worker_hostname="worker-pod-3",
        worker_heartbeat=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        last_sync_time=datetime(2024, 1, 15, 10, 29, 55, tzinfo=timezone.utc),
        last_sync_result="invalid json {",  # Malformed JSON
        last_sync_error=None,
    )
    test_db.add(sync_state)
    test_db.commit()

    status = get_sync_status(test_db)

    assert status["worker_hostname"] == "worker-pod-3"
    assert status["last_sync_result"] == {"error": "Invalid JSON in sync result"}


def test_get_sync_status_api_endpoint(client, admin_auth_override, test_db):
    """Test /api/v1/admin/sync/status endpoint."""
    # Create sync state
    sync_result = {"updated": 3, "deleted": 1, "unchanged": 7}
    sync_state = SyncState(
        id=1,
        worker_hostname="worker-pod-1",
        worker_heartbeat=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        last_sync_time=datetime(2024, 1, 15, 10, 29, 55, tzinfo=timezone.utc),
        last_sync_result=json.dumps(sync_result),
    )
    test_db.add(sync_state)
    test_db.commit()
    # Ensure data is visible to other sessions
    test_db.flush()

    # Call API - admin_auth_override fixture already sets up auth
    response = client.get("/api/v1/admin/sync/status")

    assert response.status_code == 200
    data = response.json()
    assert data["worker_hostname"] == "worker-pod-1"
    assert data["last_sync_result"] == sync_result
