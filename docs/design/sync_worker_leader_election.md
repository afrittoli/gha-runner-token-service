# Sync Worker with Leader Election

## Overview

The sync worker synchronizes GitHub Actions runner state with the local database. To prevent race conditions when running multiple replicas, it uses **PostgreSQL advisory locks** for leader election.

## Architecture

### Single Deployment Model

```
┌─────────────────────────────────────────────────────────┐
│  Kubernetes Deployment (N replicas)                     │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Pod 1      │  │   Pod 2      │  │   Pod 3      │ │
│  │              │  │              │  │              │ │
│  │ API Server ✓ │  │ API Server ✓ │  │ API Server ✓ │ │
│  │ Sync Worker  │  │ Sync Worker  │  │ Sync Worker  │ │
│  │  (LEADER) ✓  │  │  (standby)   │  │  (standby)   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│         │                  │                  │         │
└─────────┼──────────────────┼──────────────────┼─────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                    ┌────────▼────────┐
                    │   PostgreSQL    │
                    │  Advisory Lock  │
                    │   (ID: 1847..)  │
                    └─────────────────┘
```

### Key Characteristics

- **All pods run both API server and sync worker**
- **Only ONE pod becomes the sync leader** (via PostgreSQL advisory lock)
- **All pods serve API traffic** (horizontally scaled)
- **Automatic failover**: If leader dies, another pod takes over

## Leader Election Mechanism

### PostgreSQL Advisory Locks

The sync worker uses PostgreSQL's `pg_try_advisory_lock()` function:

```python
# Lock ID: 1847293847 (derived from "gharts-sync")
acquired = await pg_conn.fetchval(
    "SELECT pg_try_advisory_lock($1)", 
    1847293847
)
```

**Properties:**
- **Session-scoped**: Lock released when connection closes
- **Non-blocking**: `pg_try_advisory_lock()` returns immediately
- **Automatic cleanup**: Lock released if pod crashes/restarts
- **Database-level coordination**: Works across all replicas

### Leader Election Flow

```
Pod Startup
    │
    ├─> Start API Server (always)
    │
    ├─> Start Sync Worker
    │       │
    │       ├─> Try acquire advisory lock
    │       │
    │       ├─> Success? ──> LEADER
    │       │                  │
    │       │                  ├─> Run sync loop
    │       │                  ├─> Update heartbeat every 30s
    │       │                  └─> Store sync results in DB
    │       │
    │       └─> Failed? ──> STANDBY
    │                         │
    │                         ├─> Retry every 30s
    │                         └─> Monitor for leadership
    │
    └─> Serve API requests (all pods)
```

### Failover Scenario

```
Time  Pod 1 (Leader)    Pod 2 (Standby)    Pod 3 (Standby)
────  ───────────────    ───────────────    ───────────────
T0    Sync running       Waiting            Waiting
T1    Sync running       Waiting            Waiting
T2    💥 CRASH           Waiting            Waiting
T3    (gone)             Try lock → ✓       Try lock → ✗
T4    (gone)             LEADER             Waiting
T5    (gone)             Sync running       Waiting
```

**Failover time**: ~30 seconds (next retry attempt)

## Database Schema

### SyncState Table

Tracks the current sync leader and results:

```sql
CREATE TABLE sync_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Single row
    worker_hostname VARCHAR NOT NULL,        -- Current leader
    worker_heartbeat TIMESTAMP NOT NULL,     -- Last heartbeat
    last_sync_time TIMESTAMP,                -- Last sync completion
    last_sync_result TEXT,                   -- JSON: {updated, deleted, ...}
    last_sync_error TEXT,                    -- Error message if failed
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

**Single-row enforcement**: Only one record (id=1) can exist.

## Configuration

### Environment Variables

```bash
# Enable sync worker (default: true)
SYNC_ENABLED=true

# Sync interval in seconds (default: 120)
SYNC_INTERVAL_SECONDS=120

# Run sync on startup (default: true)
SYNC_ON_STARTUP=true

# Database connection (required for advisory locks)
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

### Helm Values

```yaml
config:
  sync:
    enabled: true
    intervalSeconds: 300
    onStartup: true

# Backend replicas (all run sync worker with leader election)
replicaCount:
  backend: 3

# HPA can scale up/down - leader election handles coordination
backend:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
```

## Monitoring

### Sync Status API

Check which pod is the current leader:

```bash
GET /api/v1/admin/sync/status

Response:
{
  "enabled": true,
  "worker_hostname": "gharts-backend-7d9f8b-abc123",
  "worker_heartbeat": "2024-01-15T10:30:00Z",
  "last_sync_time": "2024-01-15T10:29:55Z",
  "last_sync_result": {
    "updated": 3,
    "deleted": 1,
    "unchanged": 7,
    "errors": 0
  },
  "last_sync_error": null
}
```

### Logs

Leader election events:

```
# Pod becomes leader
{"event": "sync_worker_started", "leader": true, "hostname": "pod-1"}

# Pod fails to acquire lock (standby)
{"event": "sync_worker_started", "leader": false, "hostname": "pod-2"}

# Heartbeat updates
{"event": "heartbeat_updated", "hostname": "pod-1"}

# Sync completion
{"event": "sync_completed", "updated": 3, "deleted": 1}
```

## Operational Considerations

### Scaling

**Horizontal scaling is safe:**
```bash
kubectl scale deployment gharts-backend --replicas=5
```

- New pods start as standbys
- Leader election prevents duplicate syncs
- No configuration changes needed

### Rolling Updates

**Zero-downtime deployments:**
1. New pods start, try to acquire lock (fail - leader exists)
2. Old leader pod terminates, releases lock
3. One of the new pods acquires lock, becomes leader
4. Sync continues with <30s interruption

### Database Requirements

**PostgreSQL is required** for advisory locks:
- SQLite does not support advisory locks
- MySQL advisory locks work differently (not recommended)
- For development with SQLite, run single replica only

### Troubleshooting

**No sync happening:**
```bash
# Check if any pod is leader
kubectl logs -l app=gharts-backend | grep "leader.*true"

# Check sync_state table
psql -c "SELECT * FROM sync_state;"

# Check for lock contention
psql -c "SELECT * FROM pg_locks WHERE locktype = 'advisory';"
```

**Multiple leaders (should never happen):**
```bash
# This indicates a bug - advisory lock should prevent this
kubectl logs -l app=gharts-backend | grep "sync_completed" | sort
```

## Security Considerations

### Advisory Lock ID

The lock ID `1847293847` is derived from:
```python
int(hashlib.sha256(b"gharts-sync").hexdigest()[:8], 16)
```

**Why this matters:**
- Unique per application
- Prevents conflicts with other apps using advisory locks
- Stable across deployments

### Database Permissions

The sync worker requires:
- `SELECT`, `INSERT`, `UPDATE` on `sync_state` table
- `pg_try_advisory_lock()` function access (default for all users)

## Testing

### Unit Tests

```bash
# Test leader election
pytest tests/test_sync_worker.py::test_worker_acquires_leadership
pytest tests/test_sync_worker.py::test_worker_fails_to_acquire_leadership

# Test sync state tracking
pytest tests/test_sync_state_model.py
pytest tests/test_sync_status_api.py
```

### Integration Testing

```bash
# Deploy with 3 replicas
helm install gharts ./helm/gharts --set replicaCount.backend=3

# Verify only one leader
kubectl logs -l app=gharts-backend | grep "leader.*true" | wc -l
# Should output: 1

# Kill leader pod
kubectl delete pod <leader-pod-name>

# Verify new leader elected within 30s
kubectl logs -l app=gharts-backend --since=1m | grep "leader.*true"
```

## Comparison with Alternatives

### Why Not Kubernetes Leader Election?

**Considered but not chosen:**
- Requires additional RBAC permissions (Lease resources)
- More complex setup
- PostgreSQL advisory locks are simpler and sufficient

### Why Not Separate Worker Deployment?

**Original proposal, but revised:**
- ❌ More complex: two deployments to manage
- ❌ Resource overhead: separate pods just for sync
- ✅ Current approach: simpler, same container, leader election

### Why Not Distributed Locks (Redis, etcd)?

**Not needed:**
- PostgreSQL already required for application
- Advisory locks are built-in, no extra infrastructure
- Simpler operational model

## References

- PostgreSQL Advisory Locks: https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS
- Issue #33: https://github.com/afrittoli/gha-runner-token-service/issues/33
- Implementation: `app/worker.py`