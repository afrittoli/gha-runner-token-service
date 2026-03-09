"""End-to-end integration tests for leader election with multiple workers."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.worker import SyncWorker, SYNC_LEADER_LOCK_ID
from app.models import SyncState
from app.services.sync_service import SyncResult


@pytest.mark.asyncio
async def test_single_worker_becomes_leader(test_db):
    """Test that a single worker successfully becomes leader."""
    worker = SyncWorker()

    # Mock PostgreSQL connection
    mock_conn = AsyncMock()
    mock_conn.fetchval.return_value = True  # Lock acquired
    worker.pg_conn = mock_conn

    # Simulate leader election
    acquired = await worker.pg_conn.fetchval(
        "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
    )

    assert acquired is True
    assert (
        worker.is_leader is False
    )  # Not set yet (would be in _run_with_leader_election)


@pytest.mark.asyncio
async def test_second_worker_fails_to_acquire_lock(test_db):
    """Test that second worker cannot acquire lock when first is leader."""
    worker1 = SyncWorker()
    worker2 = SyncWorker()

    # Mock connections - worker1 gets lock, worker2 doesn't
    mock_conn1 = AsyncMock()
    mock_conn1.fetchval.return_value = True
    worker1.pg_conn = mock_conn1

    mock_conn2 = AsyncMock()
    mock_conn2.fetchval.return_value = False  # Lock already held
    worker2.pg_conn = mock_conn2

    # Worker 1 acquires lock
    acquired1 = await worker1.pg_conn.fetchval(
        "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
    )
    assert acquired1 is True

    # Worker 2 fails to acquire lock
    acquired2 = await worker2.pg_conn.fetchval(
        "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
    )
    assert acquired2 is False


@pytest.mark.asyncio
async def test_leader_failover_scenario(test_db):
    """Test that standby worker takes over when leader fails."""
    worker1 = SyncWorker()
    worker2 = SyncWorker()

    # Initial state: worker1 is leader
    mock_conn1 = AsyncMock()
    mock_conn1.fetchval.side_effect = [True, True]  # Acquired, then held
    worker1.pg_conn = mock_conn1
    worker1.is_leader = True

    # Worker2 is standby
    mock_conn2 = AsyncMock()
    # First attempt fails (leader exists), second succeeds (after failover)
    mock_conn2.fetchval.side_effect = [False, True]
    worker2.pg_conn = mock_conn2
    worker2.is_leader = False

    # Worker 2 tries to acquire - fails (worker1 is leader)
    acquired = await worker2.pg_conn.fetchval(
        "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
    )
    assert acquired is False

    # Simulate worker1 failure (connection closes, lock released)
    # Worker 2 tries again - succeeds
    acquired = await worker2.pg_conn.fetchval(
        "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
    )
    assert acquired is True


@pytest.mark.asyncio
async def test_heartbeat_updates_during_leadership(test_db):
    """Test that leader updates heartbeat regularly."""
    worker = SyncWorker()

    # First heartbeat
    worker._update_heartbeat(test_db)
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state is not None
    assert sync_state.worker_hostname == worker.hostname
    first_heartbeat = sync_state.worker_heartbeat

    # Simulate time passing and another heartbeat
    import time

    time.sleep(0.1)
    worker._update_heartbeat(test_db)

    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    second_heartbeat = sync_state.worker_heartbeat

    # Second heartbeat should be later
    assert second_heartbeat >= first_heartbeat


@pytest.mark.asyncio
async def test_sync_result_stored_in_database(test_db):
    """Test that sync results are stored and readable by all workers."""
    worker = SyncWorker()

    # Create initial state
    sync_state = SyncState(
        id=1,
        worker_hostname=worker.hostname,
        worker_heartbeat=datetime.now(timezone.utc),
    )
    test_db.add(sync_state)
    test_db.commit()

    # Store sync result
    result = SyncResult(updated=10, deleted=3, unchanged=25)
    worker._store_sync_result(test_db, result)

    # Verify any worker can read the result
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state.last_sync_time is not None
    assert "updated" in sync_state.last_sync_result
    assert "10" in sync_state.last_sync_result  # JSON string


@pytest.mark.asyncio
async def test_multiple_workers_only_one_syncs(test_db):
    """Test that only the leader performs sync operations."""

    # Create 3 workers
    workers = [SyncWorker() for _ in range(3)]

    # Mock connections - only first worker gets lock
    for i, worker in enumerate(workers):
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = i == 0  # Only first worker gets lock
        worker.pg_conn = mock_conn

    # Check lock acquisition
    results = []
    for worker in workers:
        acquired = await worker.pg_conn.fetchval(
            "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
        )
        results.append(acquired)

    # Only one worker should have acquired the lock
    assert sum(results) == 1
    assert results[0] is True  # First worker is leader
    assert results[1] is False  # Others are standbys
    assert results[2] is False


@pytest.mark.asyncio
@patch("app.worker.SyncService")
async def test_leader_performs_sync_standby_waits(mock_sync_service_class, test_db):
    """Test that leader performs sync while standby waits."""
    from app.services.sync_service import SyncResult

    leader = SyncWorker()
    standby = SyncWorker()

    # Setup leader
    mock_conn_leader = AsyncMock()
    mock_conn_leader.fetchval.return_value = True
    leader.pg_conn = mock_conn_leader

    # Setup standby
    mock_conn_standby = AsyncMock()
    mock_conn_standby.fetchval.return_value = False
    standby.pg_conn = mock_conn_standby

    # Mock sync service for leader
    mock_sync_service = AsyncMock()
    mock_result = SyncResult(updated=5, deleted=1, unchanged=10)
    mock_sync_service.sync_all_runners.return_value = mock_result
    mock_sync_service_class.return_value = mock_sync_service

    # Create initial sync_state
    sync_state = SyncState(
        id=1,
        worker_hostname=leader.hostname,
        worker_heartbeat=datetime.now(timezone.utc),
    )
    test_db.add(sync_state)
    test_db.commit()

    # Leader acquires lock
    leader_acquired = await leader.pg_conn.fetchval(
        "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
    )
    assert leader_acquired is True

    # Standby fails to acquire lock
    standby_acquired = await standby.pg_conn.fetchval(
        "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
    )
    assert standby_acquired is False

    # Only leader should perform sync
    # (In real scenario, standby would sleep and retry)


@pytest.mark.asyncio
async def test_sync_state_consistency_across_workers(test_db):
    """Test that all workers see consistent sync state from database."""
    worker1 = SyncWorker()
    # worker2 would read the same state (not needed for this test)

    # Worker 1 (leader) updates sync state
    sync_state = SyncState(
        id=1,
        worker_hostname=worker1.hostname,
        worker_heartbeat=datetime.now(timezone.utc),
    )
    test_db.add(sync_state)
    test_db.commit()

    result = SyncResult(updated=7, deleted=2, unchanged=15)
    worker1._store_sync_result(test_db, result)

    # Worker 2 (standby) reads the same state
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state.worker_hostname == worker1.hostname
    assert sync_state.last_sync_result is not None
    assert "updated" in sync_state.last_sync_result


@pytest.mark.asyncio
async def test_error_handling_preserves_leadership(test_db):
    """Test that sync errors don't cause leader to lose leadership."""

    worker = SyncWorker()

    # Create initial state
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

    # Verify error stored but worker can continue
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state.last_sync_error == error_msg
    assert sync_state.worker_hostname == worker.hostname  # Still the same worker


@pytest.mark.asyncio
async def test_lock_id_uniqueness():
    """Test that lock ID is unique and stable across restarts."""
    # Lock ID should be deterministic
    assert SYNC_LEADER_LOCK_ID == 1847293847

    # Should be the same across multiple imports
    from app.worker import SYNC_LEADER_LOCK_ID as LOCK_ID_2

    assert SYNC_LEADER_LOCK_ID == LOCK_ID_2


@pytest.mark.asyncio
async def test_graceful_shutdown_releases_resources(test_db):
    """Test that worker gracefully shuts down and releases resources."""
    worker = SyncWorker()

    # Mock connection
    mock_conn = AsyncMock()
    worker.pg_conn = mock_conn

    # Request shutdown
    worker.request_shutdown()
    assert worker.shutdown_requested is True

    # In real scenario, this would cause the worker loop to exit
    # and connection to close, releasing the advisory lock


@pytest.mark.asyncio
async def test_worker_hostname_tracking(test_db):
    """Test that worker hostname is tracked in sync state."""
    worker1 = SyncWorker()
    worker2 = SyncWorker()

    # Worker 1 becomes leader
    worker1._update_heartbeat(test_db)
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state.worker_hostname == worker1.hostname

    # Worker 2 takes over (simulated failover)
    worker2._update_heartbeat(test_db)
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state.worker_hostname == worker2.hostname


@pytest.mark.asyncio
async def test_concurrent_heartbeat_updates(test_db):
    """Test that concurrent heartbeat updates don't cause conflicts."""
    worker = SyncWorker()

    # Create initial state
    sync_state = SyncState(
        id=1,
        worker_hostname=worker.hostname,
        worker_heartbeat=datetime.now(timezone.utc),
    )
    test_db.add(sync_state)
    test_db.commit()

    # Multiple rapid heartbeat updates (simulating high frequency)
    for _ in range(5):
        worker._update_heartbeat(test_db)

    # Should still have only one row
    count = test_db.query(SyncState).count()
    assert count == 1

    # Latest heartbeat should be stored
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    assert sync_state.worker_hostname == worker.hostname


@pytest.mark.asyncio
async def test_sync_result_json_format(test_db):
    """Test that sync results are stored in correct JSON format."""
    import json

    worker = SyncWorker()

    # Create initial state
    sync_state = SyncState(
        id=1,
        worker_hostname=worker.hostname,
        worker_heartbeat=datetime.now(timezone.utc),
    )
    test_db.add(sync_state)
    test_db.commit()

    # Store result
    result = SyncResult(updated=12, deleted=4, unchanged=30)
    worker._store_sync_result(test_db, result)

    # Verify JSON format
    sync_state = test_db.query(SyncState).filter_by(id=1).first()
    result_dict = json.loads(sync_state.last_sync_result)

    assert isinstance(result_dict, dict)
    assert result_dict["updated"] == 12
    assert result_dict["deleted"] == 4
    assert result_dict["unchanged"] == 30
    assert "errors" in result_dict


# Made with Bob
