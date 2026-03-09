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
from datetime import datetime, timezone
from typing import Optional

import asyncpg
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.database import SessionLocal
from app.models import SyncState
from app.services.sync_service import SyncService, SyncError

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

        try:
            await self._run_with_leader_election()
        finally:
            if self.pg_conn:
                await self.pg_conn.close()
                logger.info("sync_worker_stopped", hostname=self.hostname)

    async def _run_with_leader_election(self):
        """Main loop with leader election."""
        while not self.shutdown_requested:
            try:
                # Try to acquire leadership
                acquired = await self.pg_conn.fetchval(
                    "SELECT pg_try_advisory_lock($1)", SYNC_LEADER_LOCK_ID
                )

                if acquired:
                    if not self.is_leader:
                        logger.info("leader_elected", hostname=self.hostname)
                        self.is_leader = True

                    # Run sync as leader
                    await self._run_sync_cycle()
                else:
                    if self.is_leader:
                        logger.warning("leadership_lost", hostname=self.hostname)
                        self.is_leader = False

                    logger.debug("sync_standby", hostname=self.hostname)
                    await asyncio.sleep(self.settings.sync_interval_seconds)

            except asyncpg.PostgresError as e:
                logger.error("postgres_error", error=str(e), hostname=self.hostname)
                # Connection lost - reconnect
                await self._reconnect()
            except Exception as e:
                logger.error("sync_worker_error", error=str(e), hostname=self.hostname)
                await asyncio.sleep(10)  # Back off on errors

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(asyncpg.PostgresError),
    )
    async def _reconnect(self):
        """Reconnect to PostgreSQL with retry logic."""
        if self.pg_conn:
            try:
                await self.pg_conn.close()
            except Exception:
                pass

        self.pg_conn = await asyncpg.connect(self.settings.database_url)
        self.is_leader = False
        logger.info("postgres_reconnected", hostname=self.hostname)

    async def _run_sync_cycle(self):
        """Execute a single sync cycle as leader."""
        db = SessionLocal()
        try:
            # Update heartbeat
            self._update_heartbeat(db)

            # Run sync
            sync_service = SyncService(self.settings, db)
            result = await sync_service.sync_all_runners()

            # Store result in database
            self._store_sync_result(db, result)

            logger.info("sync_cycle_completed", **result.to_dict())

            # Sleep until next cycle
            await asyncio.sleep(self.settings.sync_interval_seconds)

        except SyncError as e:
            logger.error("sync_error", error=str(e))
            self._store_sync_error(db, str(e))
            # Continue running despite sync errors
            await asyncio.sleep(self.settings.sync_interval_seconds)
        except Exception as e:
            logger.error("sync_cycle_error", error=str(e))
            self._store_sync_error(db, str(e))
            await asyncio.sleep(self.settings.sync_interval_seconds)
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

    def request_shutdown(self):
        """Request graceful shutdown (finish current cycle)."""
        logger.info("shutdown_requested", hostname=self.hostname)
        self.shutdown_requested = True


async def main():
    """Entry point for sync worker."""
    from app.logging_config import setup_logging

    setup_logging()

    worker = SyncWorker()

    # Handle shutdown signals
    def signal_handler():
        worker.request_shutdown()

    # Register signal handlers
    import signal

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s, f: signal_handler())

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("worker_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
