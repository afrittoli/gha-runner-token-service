"""Tests for SyncState model."""

import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

from app.models import SyncState


def test_sync_state_model_creation(test_db):
    """Test SyncState model can be created."""
    now = datetime.now(timezone.utc)
    sync_state = SyncState(
        id=1,
        worker_hostname="test-worker",
        worker_heartbeat=now,
    )
    test_db.add(sync_state)
    test_db.commit()

    assert sync_state.id == 1
    assert sync_state.worker_hostname == "test-worker"
    # SQLite strips timezone info, so compare without it
    assert sync_state.worker_heartbeat.replace(tzinfo=None) == now.replace(tzinfo=None)
    assert sync_state.last_sync_time is None
    assert sync_state.last_sync_result is None
    assert sync_state.last_sync_error is None


def test_sync_state_with_sync_results(test_db):
    """Test SyncState can store sync results."""
    import json

    now = datetime.now(timezone.utc)
    sync_result = json.dumps({"updated": 5, "deleted": 2, "errors": 0})

    sync_state = SyncState(
        id=1,
        worker_hostname="test-worker",
        worker_heartbeat=now,
        last_sync_time=now,
        last_sync_result=sync_result,
    )
    test_db.add(sync_state)
    test_db.commit()

    # Retrieve and verify
    retrieved = test_db.query(SyncState).filter_by(id=1).first()
    assert retrieved is not None
    assert retrieved.last_sync_result == sync_result
    assert json.loads(retrieved.last_sync_result)["updated"] == 5


def test_sync_state_update_heartbeat(test_db):
    """Test updating sync state heartbeat."""
    now = datetime.now(timezone.utc)
    sync_state = SyncState(id=1, worker_hostname="worker-1", worker_heartbeat=now)
    test_db.add(sync_state)
    test_db.commit()

    # Update heartbeat
    later = datetime.now(timezone.utc)
    sync_state.worker_heartbeat = later
    sync_state.worker_hostname = "worker-2"
    test_db.commit()

    # Verify update
    retrieved = test_db.query(SyncState).filter_by(id=1).first()
    assert retrieved.worker_hostname == "worker-2"
    # SQLite strips timezone info
    assert retrieved.worker_heartbeat.replace(tzinfo=None) == later.replace(tzinfo=None)


def test_sync_state_error_tracking(test_db):
    """Test sync state can track errors."""
    now = datetime.now(timezone.utc)
    error_msg = "GitHub API rate limit exceeded"

    sync_state = SyncState(
        id=1,
        worker_hostname="test-worker",
        worker_heartbeat=now,
        last_sync_error=error_msg,
    )
    test_db.add(sync_state)
    test_db.commit()

    retrieved = test_db.query(SyncState).filter_by(id=1).first()
    assert retrieved.last_sync_error == error_msg


def test_sync_state_single_row_enforcement(test_db):
    """Test that only one sync_state row should exist (id=1).

    Note: This test verifies application-level enforcement.
    In production, PostgreSQL CHECK constraint would enforce this at DB level.
    """
    now = datetime.now(timezone.utc)

    # First row with id=1 succeeds
    sync_state1 = SyncState(id=1, worker_hostname="worker-1", worker_heartbeat=now)
    test_db.add(sync_state1)
    test_db.commit()

    # Attempting to create another row with id=1 should fail (duplicate primary key)
    sync_state2 = SyncState(id=1, worker_hostname="worker-2", worker_heartbeat=now)
    test_db.add(sync_state2)

    with pytest.raises(IntegrityError):
        test_db.commit()

    test_db.rollback()

    # Verify only one row exists
    count = test_db.query(SyncState).count()
    assert count == 1


def test_sync_state_timestamps(test_db):
    """Test that timestamps are automatically set."""
    now = datetime.now(timezone.utc)
    sync_state = SyncState(id=1, worker_hostname="test-worker", worker_heartbeat=now)
    test_db.add(sync_state)
    test_db.commit()

    assert sync_state.created_at is not None
    assert sync_state.updated_at is not None
    assert sync_state.created_at <= sync_state.updated_at


def test_sync_state_query_by_heartbeat(test_db):
    """Test querying sync state by heartbeat age."""
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    old_time = now - timedelta(minutes=10)

    sync_state = SyncState(
        id=1, worker_hostname="test-worker", worker_heartbeat=old_time
    )
    test_db.add(sync_state)
    test_db.commit()

    # Query for stale heartbeats (older than 5 minutes)
    threshold = now - timedelta(minutes=5)
    stale = (
        test_db.query(SyncState).filter(SyncState.worker_heartbeat < threshold).first()
    )

    assert stale is not None
    assert stale.worker_hostname == "test-worker"


# Made with Bob
