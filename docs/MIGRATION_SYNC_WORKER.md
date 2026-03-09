# Migration Guide: Sync Worker with Leader Election

This guide covers migrating from the old sync implementation to the new leader election-based sync worker.

## Overview

**Old Implementation:**
- Each API pod ran its own sync loop
- Race conditions when multiple replicas ran simultaneously
- Manual sync trigger endpoint (`POST /api/v1/admin/sync/trigger`)

**New Implementation:**
- All pods run both API server and sync worker
- PostgreSQL advisory locks ensure only one pod performs sync (leader)
- Automatic failover if leader pod fails
- Database-driven sync status for consistency across replicas
- Manual sync trigger removed (no longer needed)

## Prerequisites

- **PostgreSQL database required** (SQLite does not support advisory locks)
- Database migration to add `sync_state` table
- Prometheus metrics endpoint available at `/metrics`

## Migration Steps

### 1. Database Migration

The `sync_state` table is created automatically by Alembic migrations:

```bash
# In your deployment, migrations run automatically on startup
# Or run manually:
alembic upgrade head
```

**New table schema:**
```sql
CREATE TABLE sync_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    worker_hostname VARCHAR NOT NULL,
    worker_heartbeat TIMESTAMP NOT NULL,
    last_sync_time TIMESTAMP,
    last_sync_result TEXT,
    last_sync_error TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### 2. Update Helm Chart

**No configuration changes required!** The new implementation is backward compatible:

```yaml
# helm/gharts/values.yaml
config:
  sync:
    enabled: true              # Same as before
    intervalSeconds: 300       # Same as before
    onStartup: true           # Same as before
```

**What changed internally:**
- Leader election happens automatically
- Only one pod performs sync (the leader)
- Other pods are standbys, ready to take over

### 3. Deploy New Version

```bash
# Standard Helm upgrade
helm upgrade gharts ./helm/gharts \
  --namespace gharts \
  --values your-values.yaml
```

**Rolling update behavior:**
1. New pods start, attempt to acquire leadership
2. Old leader pod terminates, releases advisory lock
3. One new pod acquires lock, becomes leader
4. Sync continues with minimal interruption (~30 seconds)

### 4. Verify Migration

#### Check Sync Status

```bash
# API endpoint (works from any pod)
curl http://gharts-backend/api/v1/admin/sync/status

# Expected response:
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

#### Check Leader Election

```bash
# Only ONE pod should show leader=true
kubectl logs -l app=gharts-backend | grep "leader_elected"

# Example output:
# gharts-backend-7d9f8b-abc123: {"event": "leader_elected", "hostname": "gharts-backend-7d9f8b-abc123"}
```

#### Check Metrics

```bash
# Metrics endpoint
curl http://gharts-backend/metrics | grep gharts_sync

# Key metrics to check:
# gharts_sync_leadership_status{hostname="..."} 1.0  # Leader
# gharts_sync_leadership_status{hostname="..."} 0.0  # Standby
# gharts_sync_last_success_timestamp 1705318195.0
# gharts_sync_duration_seconds_bucket{le="30.0"} 5
```

### 5. Remove Manual Sync Trigger (If Used)

The manual sync trigger endpoint has been removed:

```bash
# This endpoint NO LONGER EXISTS:
# POST /api/v1/admin/sync/trigger

# Reason: Not needed with leader election
# Sync runs automatically on the leader pod
```

**If you have automation calling this endpoint:**
- Remove the calls (sync happens automatically)
- Or use the status endpoint to verify sync is working

## Rollback Plan

If you need to rollback to the old version:

```bash
# Rollback Helm release
helm rollback gharts -n gharts

# The sync_state table will remain but won't be used
# No data loss - old implementation ignores the new table
```

## Configuration Changes

### Environment Variables (No Changes)

All existing environment variables work the same:

```bash
SYNC_ENABLED=true                    # Enable/disable sync
SYNC_INTERVAL_SECONDS=300            # Sync interval
SYNC_ON_STARTUP=true                 # Run sync on startup
DATABASE_URL=postgresql://...        # Required for advisory locks
```

### Helm Values (No Changes)

```yaml
config:
  sync:
    enabled: true
    intervalSeconds: 300
    onStartup: true

# Scaling works automatically with leader election
replicaCount:
  backend: 3  # Can scale up/down freely

backend:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10  # Leader election handles coordination
```

## Monitoring and Alerting

### Prometheus Metrics

**Key metrics to monitor:**

```promql
# Sync worker health
gharts_sync_leadership_status == 1  # Should have exactly 1 leader

# Sync success rate
rate(gharts_sync_errors_total[5m]) < 0.1  # Low error rate

# Sync duration
histogram_quantile(0.95, gharts_sync_duration_seconds_bucket) < 60  # P95 < 60s

# Leader election stability
rate(gharts_leader_election_transitions_total[5m]) < 0.01  # Stable leadership
```

### Grafana Dashboard

Example queries for dashboard:

```promql
# Current leader
gharts_sync_leadership_status{hostname=~".*"} == 1

# Sync operations per minute
rate(gharts_sync_runners_updated_total[1m]) * 60

# Time since last successful sync
time() - gharts_sync_last_success_timestamp

# Advisory lock status
gharts_db_advisory_lock_held{lock_id="1847293847"}
```

### Alerts

**Recommended alerts:**

```yaml
# No leader elected
- alert: SyncNoLeader
  expr: sum(gharts_sync_leadership_status) == 0
  for: 2m
  annotations:
    summary: "No sync worker leader elected"

# Sync failing
- alert: SyncFailing
  expr: rate(gharts_sync_errors_total[5m]) > 0.1
  for: 5m
  annotations:
    summary: "Sync worker experiencing errors"

# Sync stale
- alert: SyncStale
  expr: time() - gharts_sync_last_success_timestamp > 600
  for: 5m
  annotations:
    summary: "Sync hasn't completed in 10 minutes"

# Multiple leaders (should never happen)
- alert: SyncMultipleLeaders
  expr: sum(gharts_sync_leadership_status) > 1
  for: 1m
  severity: critical
  annotations:
    summary: "Multiple sync leaders detected - advisory lock failure"
```

## Troubleshooting

### No Sync Happening

**Symptoms:**
- `last_sync_time` not updating
- No leader elected

**Diagnosis:**
```bash
# Check if any pod is leader
kubectl logs -l app=gharts-backend | grep "leader.*true"

# Check sync_state table
kubectl exec -it gharts-backend-xxx -- \
  psql $DATABASE_URL -c "SELECT * FROM sync_state;"

# Check for errors
kubectl logs -l app=gharts-backend | grep -i error
```

**Common causes:**
1. **Database connection issues** - Check DATABASE_URL
2. **PostgreSQL not available** - Verify database is running
3. **All pods failing to start** - Check pod logs

**Resolution:**
```bash
# Restart pods to retry leader election
kubectl rollout restart deployment/gharts-backend -n gharts
```

### Multiple Leaders (Critical)

**Symptoms:**
- Multiple pods showing `leader_elected` in logs
- Duplicate sync operations

**This should never happen** - indicates advisory lock failure.

**Diagnosis:**
```bash
# Check advisory locks in PostgreSQL
kubectl exec -it postgres-pod -- \
  psql -c "SELECT * FROM pg_locks WHERE locktype = 'advisory';"

# Should show only ONE lock with lockid=1847293847
```

**Resolution:**
1. **Immediate:** Scale down to 1 replica
   ```bash
   kubectl scale deployment gharts-backend --replicas=1 -n gharts
   ```

2. **Investigate:** Check PostgreSQL logs for connection issues

3. **Scale back up** once issue is resolved

### Sync Errors

**Symptoms:**
- `last_sync_error` populated
- `gharts_sync_errors_total` increasing

**Diagnosis:**
```bash
# Check error details
curl http://gharts-backend/api/v1/admin/sync/status | jq '.last_sync_error'

# Check logs
kubectl logs -l app=gharts-backend | grep sync_error
```

**Common causes:**
1. **GitHub API rate limit** - Wait for reset or increase rate limit
2. **GitHub App authentication** - Check app credentials
3. **Network issues** - Check connectivity to GitHub

### Leadership Flapping

**Symptoms:**
- Frequent leadership transitions
- `gharts_leader_election_transitions_total` increasing rapidly

**Diagnosis:**
```bash
# Check transition rate
kubectl logs -l app=gharts-backend | grep -E "leader_elected|leadership_lost"

# Check pod restarts
kubectl get pods -l app=gharts-backend
```

**Common causes:**
1. **Pod crashes** - Check pod logs for errors
2. **Database connection instability** - Check PostgreSQL health
3. **Resource constraints** - Check CPU/memory limits

**Resolution:**
- Fix underlying pod stability issues
- Increase resource limits if needed
- Check database connection pool settings

## Performance Considerations

### Scaling

**Horizontal scaling is safe:**
```bash
# Scale up
kubectl scale deployment gharts-backend --replicas=10 -n gharts

# Scale down
kubectl scale deployment gharts-backend --replicas=2 -n gharts
```

**Impact:**
- Only one pod performs sync (the leader)
- Other pods serve API traffic
- No performance degradation from multiple replicas

### Resource Usage

**Per-pod resources:**
- **Leader pod:** Slightly higher CPU during sync
- **Standby pods:** Minimal overhead (just monitoring)

**Recommended limits:**
```yaml
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

### Database Load

**Advisory lock overhead:**
- Minimal - single lock acquisition per sync interval
- No additional queries during standby

**Sync state table:**
- Single row, updated every sync cycle
- Negligible storage and I/O impact

## FAQ

### Q: Can I run with SQLite?

**A:** Only with a single replica. SQLite doesn't support advisory locks, so leader election won't work with multiple replicas.

```yaml
# For development with SQLite
replicaCount:
  backend: 1  # Must be 1
```

### Q: What happens during rolling updates?

**A:** Seamless transition:
1. New pods start as standbys
2. Old leader pod terminates, releases lock
3. New pod acquires lock within ~30 seconds
4. Sync continues with minimal interruption

### Q: Can I force a specific pod to be leader?

**A:** No, and you shouldn't need to. Leader election is automatic and handles failover. If you need to change the leader, restart the current leader pod.

### Q: How do I disable sync temporarily?

**A:** Set `SYNC_ENABLED=false` or update Helm values:

```yaml
config:
  sync:
    enabled: false
```

Then redeploy. All pods will skip sync operations.

### Q: What if the leader pod crashes?

**A:** Automatic failover:
1. Leader pod crashes, connection closes
2. Advisory lock automatically released
3. Standby pod acquires lock within ~30 seconds
4. New leader continues sync operations

### Q: Can I monitor which pod is the leader?

**A:** Yes, multiple ways:

```bash
# API endpoint
curl http://gharts-backend/api/v1/admin/sync/status | jq '.worker_hostname'

# Metrics
curl http://gharts-backend/metrics | grep gharts_sync_leadership_status

# Logs
kubectl logs -l app=gharts-backend | grep leader_elected
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/afrittoli/gha-runner-token-service/issues
- Documentation: https://github.com/afrittoli/gha-runner-token-service/tree/main/docs