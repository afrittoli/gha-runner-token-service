"""Dedicated sync worker with leader election.

This module implements a standalone sync worker that uses PostgreSQL advisory
locks for leader election. Only the elected leader performs sync operations,
while standby workers monitor for leadership changes.

Usage:
    python -m app.worker
"""

import asyncio
import json
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import structlog
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.database import SessionLocal
from app.models import SyncState
from app.services.sync_service import SyncService, SyncError
from app.metrics import (
    sync_leadership_status,
    sync_last_success_timestamp,
    sync_duration_seconds,
    sync_runners_updated,
    sync_runners_deleted,
    sync_runners_unchanged,
    sync_errors_total,
    sync_heartbeat_timestamp,
    leader_election_attempts,
    leader_election_transitions,
    db_advisory_lock_held,
)

logger = structlog.get_logger()

# Stable lock ID for sync leader election
# Derived from: hash("gharts-sync-leader") & 0x7FFFFFFF
SYNC_LEADER_LOCK_ID = 1847293847


class LeaderElectionError(Exception):
    """Raised when leader election fails."""

    pass


class SyncWorker:
    """Dedicated sync worker with leader election.

    Uses PostgreSQL advisory locks to ensure only one worker performs sync
    operations at a time. Standby workers monitor for leadership changes
    and take over if the leader fails.
    """

    def __init__(self):
        self.settings = get_settings()
        self.hostname = socket.gethostname()
        self.is_leader = False
        self.pg_conn: Optional[asyncpg.Connection] = None
        self.shutdown_requested = False

    async def start(self):
        """Start the sync worker with leader election."""
        logger.info("sync_worker_starting", hostname=self.hostname)

        # Check if we're using PostgreSQL (required for leader election)
        if not self.settings.database_url.startswith(("postgresql://", "postgres://")):
            logger.warning(
                "sync_worker_skipped",
                reason="Leader election requires PostgreSQL, not SQLite",
                hostname=self.hostname,
            )
            return

        # Establish persistent PostgreSQL connection for advisory lock
        try:
            self.pg_conn = await asyncpg.connect(self.settings.database_url)
            logger.info("postgres_connected", hostname=self.hostname)
        except Exception as e:
            logger.error(
                "postgres_connection_failed",
                error=str(e),
                hostname=self.hostname,
            )
            raise

        # Initialize sync_state record on startup
        self._initialize_sync_state()

        try:
            await self._run_with_leader_election()
        finally:
            if self.pg_conn:
                await self.pg_conn.close()
                logger.info("sync_worker_stopped", hostname=self.hostname)

    async def _run_with_leader_election(self):
        """Main loop with leader election."""
        backoff_seconds = 10  # Initial backoff for outer loop errors
        max_backoff = 300  # Max 5 minutes

        while not self.shutdown_requested:
            try:
                # Try to acquire leadership
                acquired = await self.pg_conn.fetchval(
                    "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
                )

                # Record election attempt
                leader_election_attempts.labels(
                    result="success" if acquired else "failed"
                ).inc()

                if acquired:
                    if not self.is_leader:
                        logger.info("leader_elected", hostname=self.hostname)
                        # Record leadership transition
                        leader_election_transitions.labels(
                            from_state="standby", to_state="leader"
                        ).inc()
                        self.is_leader = True

                    # Update metrics
                    sync_leadership_status.labels(hostname=self.hostname).set(1)
                    db_advisory_lock_held.labels(
                        hostname=self.hostname, lock_id=str(SYNC_LEADER_LOCK_ID)
                    ).set(1)

                    # Run sync as leader
                    await self._run_sync_cycle()
                    # Reset backoff on successful cycle
                    backoff_seconds = 10
                else:
                    if self.is_leader:
                        logger.warning("leadership_lost", hostname=self.hostname)
                        # Record leadership transition
                        leader_election_transitions.labels(
                            from_state="leader", to_state="standby"
                        ).inc()
                        self.is_leader = False

                    # Update metrics
                    sync_leadership_status.labels(hostname=self.hostname).set(0)
                    db_advisory_lock_held.labels(
                        hostname=self.hostname, lock_id=str(SYNC_LEADER_LOCK_ID)
                    ).set(0)

                    logger.debug("sync_standby", hostname=self.hostname)
                    await asyncio.sleep(self.settings.sync_interval_seconds)
                    # Reset backoff on successful standby cycle
                    backoff_seconds = 10

            except asyncpg.PostgresError as e:
                logger.error("postgres_error", error=str(e), hostname=self.hostname)
                sync_errors_total.labels(error_type="postgres_error").inc()
                # Connection lost - reconnect
                await self._reconnect()
                # Reset backoff after successful reconnect
                backoff_seconds = 10
            except RetryError as e:
                # Reconnection exhausted all retries
                logger.error(
                    "reconnect_exhausted",
                    error=str(e),
                    hostname=self.hostname,
                    backoff_seconds=backoff_seconds,
                )
                sync_errors_total.labels(error_type="reconnect_exhausted").inc()
                # Use exponential backoff for outer loop
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, max_backoff)
            except Exception as e:
                logger.error("sync_worker_error", error=str(e), hostname=self.hostname)
                sync_errors_total.labels(error_type="worker_error").inc()
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, max_backoff)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(asyncpg.PostgresError),
    )
    async def _reconnect(self):
        """Reconnect to PostgreSQL with retry logic."""
        # Clear connection reference first
        old_conn = self.pg_conn
        self.pg_conn = None

        # Reset leadership state and metrics immediately
        self.is_leader = False
        sync_leadership_status.labels(hostname=self.hostname).set(0)
        db_advisory_lock_held.labels(
            hostname=self.hostname, lock_id=str(SYNC_LEADER_LOCK_ID)
        ).set(0)

        # Close old connection
        if old_conn:
            try:
                await old_conn.close()
            except Exception:
                pass

        # Reconnect with retry logic (will raise RetryError if exhausted)
        self.pg_conn = await asyncpg.connect(self.settings.database_url)
        logger.info("postgres_reconnected", hostname=self.hostname)

    async def _run_sync_cycle(self):
        """Execute a single sync cycle as leader."""
        db = SessionLocal()
        start_time = time.time()

        try:
            # Update heartbeat
            self._update_heartbeat(db)

            # Run sync with timing
            sync_service = SyncService(self.settings, db)
            result = await sync_service.sync_all_runners()

            # Record sync duration
            duration = time.time() - start_time
            sync_duration_seconds.observe(duration)

            # Update metrics
            sync_runners_updated.inc(result.updated)
            sync_runners_deleted.inc(result.deleted)
            sync_runners_unchanged.inc(result.unchanged)
            sync_last_success_timestamp.set(time.time())

            # Store result in database
            self._store_sync_result(db, result)

            logger.info("sync_cycle_completed", **result.to_dict())

            # Sleep until next cycle
            await asyncio.sleep(self.settings.sync_interval_seconds)

        except SyncError as e:
            logger.error("sync_error", error=str(e))
            sync_errors_total.labels(error_type="sync_error").inc()
            self._store_sync_error(db, str(e))
            # Continue running despite sync errors
            await asyncio.sleep(self.settings.sync_interval_seconds)
        except Exception as e:
            logger.error("sync_cycle_error", error=str(e))
            sync_errors_total.labels(error_type="sync_cycle_error").inc()
            self._store_sync_error(db, str(e))
            await asyncio.sleep(self.settings.sync_interval_seconds)
        finally:
            db.close()

    def _initialize_sync_state(self):
        """Initialize sync_state record on worker startup."""
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            sync_state = db.query(SyncState).filter_by(id=1).first()
            if not sync_state:
                sync_state = SyncState(
                    id=1,
                    worker_hostname=self.hostname,
                    worker_heartbeat=now,
                )
                db.add(sync_state)
                db.commit()
                logger.info(
                    "sync_state_initialized",
                    hostname=self.hostname,
                )
        finally:
            db.close()

    def _update_heartbeat(self, db):
        """Update worker heartbeat in sync_state table."""
        now = datetime.now(timezone.utc)

        # Get or create sync_state row
        sync_state = db.query(SyncState).filter_by(id=1).first()
        if sync_state:
            sync_state.worker_hostname = self.hostname
            sync_state.worker_heartbeat = now
            sync_state.updated_at = now
        else:
            sync_state = SyncState(
                id=1,
                worker_hostname=self.hostname,
                worker_heartbeat=now,
            )
            db.add(sync_state)

        db.commit()

        # Update heartbeat metric
        sync_heartbeat_timestamp.labels(hostname=self.hostname).set(now.timestamp())

    def _store_sync_result(self, db, result):
        """Store sync result in database."""
        now = datetime.now(timezone.utc)

        sync_state = db.query(SyncState).filter_by(id=1).first()
        if sync_state:
            sync_state.last_sync_time = now
            sync_state.last_sync_result = json.dumps(result.to_dict())
            sync_state.last_sync_error = None
            sync_state.updated_at = now
            db.commit()

    def _store_sync_error(self, db, error: str):
        """Store sync error in database."""
        now = datetime.now(timezone.utc)

        sync_state = db.query(SyncState).filter_by(id=1).first()
        if sync_state:
            sync_state.last_sync_error = error
            sync_state.updated_at = now
            db.commit()
        else:
            # Create sync_state if it doesn't exist
            # This shouldn't happen but handle it gracefully
            logger.warning(
                "sync_state_missing_during_error_store",
                hostname=self.hostname,
            )
            sync_state = SyncState(
                id=1,
                worker_hostname=self.hostname,
                worker_heartbeat=now,
                last_sync_error=error,
            )
            db.add(sync_state)
            db.commit()

    def request_shutdown(self):
        """Request graceful shutdown (finish current cycle)."""
        logger.info("shutdown_requested", hostname=self.hostname)
        self.shutdown_requested = True


async def main():
    """Entry point for sync worker."""
    from app.logging_config import setup_logging
    import signal

    setup_logging()

    worker = SyncWorker()

    # Get the event loop
    loop = asyncio.get_running_loop()

    # Handle shutdown signals
    def signal_handler():
        worker.request_shutdown()

    # Register signal handlers using loop.add_signal_handler()
    # This is the correct way for async code
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("worker_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
