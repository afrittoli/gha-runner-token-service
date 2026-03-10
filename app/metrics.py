"""Prometheus metrics for monitoring sync worker and API."""

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Sync worker metrics
sync_leadership_status = Gauge(
    "gharts_sync_leadership_status",
    "Current leadership status (1=leader, 0=standby)",
    ["hostname"],
)

sync_last_success_timestamp = Gauge(
    "gharts_sync_last_success_timestamp",
    "Timestamp of last successful sync (Unix time)",
)

sync_duration_seconds = Histogram(
    "gharts_sync_duration_seconds",
    "Time spent performing sync operation",
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

sync_runners_updated = Counter(
    "gharts_sync_runners_updated_total",
    "Total number of runners updated during sync",
)

sync_runners_deleted = Counter(
    "gharts_sync_runners_deleted_total",
    "Total number of runners deleted during sync",
)

sync_runners_unchanged = Counter(
    "gharts_sync_runners_unchanged_total",
    "Total number of runners unchanged during sync",
)

sync_errors_total = Counter(
    "gharts_sync_errors_total",
    "Total number of sync errors",
    ["error_type"],
)

sync_heartbeat_timestamp = Gauge(
    "gharts_sync_heartbeat_timestamp",
    "Timestamp of last heartbeat update (Unix time)",
    ["hostname"],
)

# Leader election metrics
leader_election_attempts = Counter(
    "gharts_leader_election_attempts_total",
    "Total number of leader election attempts",
    ["result"],  # success, failed
)

leader_election_transitions = Counter(
    "gharts_leader_election_transitions_total",
    "Total number of leadership transitions",
    ["from_state", "to_state"],  # standby->leader, leader->standby
)

# Database metrics
db_advisory_lock_held = Gauge(
    "gharts_db_advisory_lock_held",
    "Whether this instance holds the advisory lock (1=yes, 0=no)",
    ["hostname", "lock_id"],
)


def get_metrics() -> tuple[bytes, str]:
    """Generate Prometheus metrics in text format.

    Returns:
        Tuple of (metrics_bytes, content_type)
    """
    return generate_latest(), CONTENT_TYPE_LATEST
