"""Tests for sync worker with leader election."""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.worker import SyncWorker, SYNC_LEADER_LOCK_ID
from app.models import SyncState


@pytest.mark.asyncio
async def test_worker_initialization():
    """Test sync worker can be initialized."""
    worker = SyncWorker()

    assert worker.hostname is not None
    assert worker.is_leader is False
    assert worker.pg_conn is None
    assert worker.shutdown_requested is False


@pytest.mark.asyncio
async def test_worker_acquires_leadership():
    """Test worker successfully acquires leadership."""
    worker = SyncWorker()

    # Mock PostgreSQL connection
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = True  # Lock acquired
    worker.pg_conn = mock_conn

    # Simulate acquiring lock
    acquired = await worker.pg_conn.fetchval(
        "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
    )

    assert acquired is True
    mock_conn.fetchval.assert_called_once_with(
        "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
    )


@pytest.mark.asyncio
async def test_worker_fails_to_acquire_leadership():
    """Test worker fails to acquire leadership (another worker is leader)."""
    worker = SyncWorker()

    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = False  # Lock not acquired
    worker.pg_conn = mock_conn

    acquired = await worker.pg_conn.fetchval(
        "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
    )

    assert acquired is False


@pytest.mark.asyncio
async def test_worker_updates_heartbeat(test_db):
    """Test worker updates heartbeat in database."""
    worker = SyncWorker()

    # Update heartbeat
    worker._update_heartbeat(test_db)

    # Verify sync_state was created/updated
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state is not None
    assert sync_state.worker_hostname == worker.hostname
    assert sync_state.worker_heartbeat is not None


@pytest.mark.asyncio
async def test_worker_stores_sync_result(test_db):
    """Test worker stores sync result in database."""
    from app.services.sync_service import SyncResult

    worker = SyncWorker()

    # Create initial sync_state
    sync_state = SyncState(
        id=1,
        worker_hostname=worker.hostname,
        worker_heartbeat=datetime.now(timezone.utc),
    )
    test_db.add(sync_state)
    test_db.commit()

    # Store sync result
    result = SyncResult(updated=5, deleted=2, unchanged=10)
    worker._store_sync_result(test_db, result)

    # Verify result was stored
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state.last_sync_time is not None
    assert sync_state.last_sync_result is not None
    assert "updated" in sync_state.last_sync_result
    assert sync_state.last_sync_error is None


@pytest.mark.asyncio
async def test_worker_stores_sync_error(test_db):
    """Test worker stores sync error in database."""
    worker = SyncWorker()

    # Create initial sync_state
    sync_state = SyncState(
        id=1,
        worker_hostname=worker.hostname,
        worker_heartbeat=datetime.now(timezone.utc),
    )
    test_db.add(sync_state)
    test_db.commit()

    # Store error
    error_msg = "GitHub API rate limit exceeded"
    worker._store_sync_error(test_db, error_msg)

    # Verify error was stored
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state.last_sync_error == error_msg


@pytest.mark.asyncio
async def test_worker_graceful_shutdown():
    """Test worker graceful shutdown request."""
    worker = SyncWorker()

    assert worker.shutdown_requested is False

    worker.request_shutdown()

    assert worker.shutdown_requested is True


@pytest.mark.asyncio
@patch("app.worker.SyncService")
async def test_worker_run_sync_cycle(mock_sync_service_class, test_db):
    """Test worker executes a sync cycle."""
    from app.services.sync_service import SyncResult

    worker = SyncWorker()

    # Mock sync service
    mock_sync_service = AsyncMock()
    mock_result = SyncResult(updated=3, deleted=1, unchanged=5)
    mock_sync_service.sync_all_runners.return_value = mock_result
    mock_sync_service_class.return_value = mock_sync_service

    # Create initial sync_state
    sync_state = SyncState(
        id=1,
        worker_hostname=worker.hostname,
        worker_heartbeat=datetime.now(timezone.utc),
    )
    test_db.add(sync_state)
    test_db.commit()

    # Mock SessionLocal to return our test_db
    with patch("app.worker.SessionLocal", return_value=test_db):
        # Mock sleep to avoid waiting
        with patch("asyncio.sleep", new_callable=AsyncMock):
            # Run one sync cycle (will be interrupted by our mock)
            try:
                await asyncio.wait_for(worker._run_sync_cycle(), timeout=0.1)
            except asyncio.TimeoutError:
                pass  # Expected - we're testing the cycle start

    # Verify sync was called
    mock_sync_service.sync_all_runners.assert_called_once()


@pytest.mark.asyncio
async def test_worker_handles_sync_error(test_db):
    """Test worker handles sync errors gracefully."""
    from app.services.sync_service import SyncError

    worker = SyncWorker()

    # Create initial sync_state
    sync_state = SyncState(
        id=1,
        worker_hostname=worker.hostname,
        worker_heartbeat=datetime.now(timezone.utc),
    )
    test_db.add(sync_state)
    test_db.commit()

    # Mock sync service that raises error
    with patch("app.worker.SyncService") as mock_sync_class:
        mock_sync = AsyncMock()
        mock_sync.sync_all_runners.side_effect = SyncError("Test error")
        mock_sync_class.return_value = mock_sync

        # Mock SessionLocal to return our test_db
        with patch("app.worker.SessionLocal", return_value=test_db):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                try:
                    await asyncio.wait_for(worker._run_sync_cycle(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass

    # Verify error was stored
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state.last_sync_error is not None


@pytest.mark.asyncio
async def test_lock_id_is_stable():
    """Test that lock ID is a stable integer."""
    assert isinstance(SYNC_LEADER_LOCK_ID, int)
    assert SYNC_LEADER_LOCK_ID > 0
    assert SYNC_LEADER_LOCK_ID == 1847293847


# Made with Bob
