# GitHub Sync Mechanism Design

## Problem Statement

The Runner Token Service maintains a local database of runner information that can become stale:
- Runners may be deleted directly from GitHub (bypassing the service)
- Ephemeral runners auto-delete after completing a job
- Runner status (online/offline) changes independently
- Pending runners may never register or fail silently
- **Runners may be configured with labels that violate policy**

Currently, sync is triggered manually via `python -m app.cli sync-github`. This document designs an automated sync mechanism with label policy enforcement.

## Requirements

### Functional
1. Keep runner status in sync with GitHub (pending, online, offline, deleted)
2. Detect runners deleted outside the service
3. Update `github_runner_id` when pending runners register
4. Clear expired registration tokens
5. Support both automatic and manual sync triggers
6. **Enforce label policies by detecting and deleting violating runners**
7. **Log security events for policy violations**

### Non-Functional
1. Minimize GitHub API calls (rate limiting: 5000/hour for apps)
2. Handle API failures gracefully
3. Observable (logging, metrics)
4. Configurable sync interval

## Design Options

### Option A: Periodic Polling (Recommended)

Background task that periodically syncs all runners with GitHub.

**Pros:**
- Simple to implement
- Works with any GitHub setup
- No additional infrastructure needed
- Easy to debug and monitor

**Cons:**
- Delay between actual state and detected state
- Consumes API quota even when nothing changes
- Not real-time

### Option B: GitHub Webhooks

Configure GitHub webhooks to notify service of runner events.

**Pros:**
- Real-time updates
- No polling overhead
- Minimal API calls

**Cons:**
- Requires public endpoint or webhook relay
- Additional infrastructure (ngrok for dev, proper ingress for prod)
- Webhook delivery can fail/delay
- More complex setup and debugging
- GitHub doesn't have webhooks for all runner events

### Option C: Hybrid (Polling + Webhooks)

Use webhooks for real-time updates with periodic polling as fallback.

**Pros:**
- Best of both worlds
- Resilient to webhook failures

**Cons:**
- Most complex to implement
- Requires webhook infrastructure

## Implemented Solution: Hybrid (Polling + Webhooks)

The implementation uses a hybrid approach:

1. **Periodic Polling (every 2 minutes)** - Primary enforcement mechanism
   - Syncs runner status with GitHub
   - Validates runner labels against user's policy
   - **Automatically deletes runners with policy violations**
   - Logs security events for all violations

2. **Webhook Handler (workflow_job events)** - Secondary enforcement
   - Catches violations that slip through the sync window
   - Triggers on `in_progress` action (when job starts)
   - Fetches runner's actual labels from GitHub API
   - Validates against user's label policy
   - Configurable response: audit-only or cancel workflow

## Implementation Design

### Components

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI App                          │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │  API Endpoints  │  │  Background     │              │
│  │  (runners.py)   │  │  Sync Task      │              │
│  └────────┬────────┘  └────────┬────────┘              │
│           │                    │                        │
│           ▼                    ▼                        │
│  ┌─────────────────────────────────────┐               │
│  │         SyncService                  │               │
│  │  - sync_all_runners()               │               │
│  │  - sync_runner(runner_id)           │               │
│  │  - cleanup_orphaned_runners()       │               │
│  └────────────────┬────────────────────┘               │
│                   │                                     │
│           ┌───────┴───────┐                            │
│           ▼               ▼                            │
│  ┌─────────────┐  ┌─────────────┐                     │
│  │  Database   │  │  GitHub     │                     │
│  │  (SQLite)   │  │  API        │                     │
│  └─────────────┘  └─────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### Configuration

Settings in `app/config.py`:

```python
# Sync Configuration
sync_enabled: bool = Field(
    default=True, description="Enable background runner sync with GitHub"
)
sync_interval_seconds: int = Field(
    default=120, description="Seconds between sync cycles (default: 2 min)"
)
sync_on_startup: bool = Field(
    default=True, description="Run sync immediately on startup"
)

# Webhook Configuration
github_webhook_secret: str = Field(
    default="", description="GitHub webhook secret for signature verification"
)

# Label Policy Enforcement
label_policy_enforcement: str = Field(
    default="audit",
    description="Label policy enforcement mode: 'audit' (log only) or 'enforce' (cancel workflow)"
)
```

**Environment Variables:**
- `SYNC_ENABLED` - Enable/disable background sync (default: true)
- `SYNC_INTERVAL_SECONDS` - Sync interval in seconds (default: 120)
- `SYNC_ON_STARTUP` - Run sync on application startup (default: true)
- `GITHUB_WEBHOOK_SECRET` - Secret for verifying webhook signatures
- `LABEL_POLICY_ENFORCEMENT` - `audit` or `enforce`

### SyncService

New service in `app/services/sync_service.py`:

```python
class SyncService:
    """Service for synchronizing runner state with GitHub."""

    async def sync_all_runners(self) -> SyncResult:
        """
        Sync all non-deleted runners with GitHub.

        Returns:
            SyncResult with counts of updated, deleted, unchanged runners
        """

    async def sync_runner(self, runner_id: str) -> Optional[Runner]:
        """
        Sync a single runner with GitHub.

        Args:
            runner_id: Internal runner UUID

        Returns:
            Updated runner or None if not found
        """

    async def cleanup_expired_tokens(self) -> int:
        """
        Clear expired registration tokens.

        Returns:
            Number of tokens cleared
        """
```

### Background Task

Using FastAPI's lifespan for background task management:

```python
# app/main.py
from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    if settings.sync_enabled:
        sync_task = asyncio.create_task(run_sync_loop(settings))

    yield

    # Shutdown
    if settings.sync_enabled:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass

async def run_sync_loop(settings: Settings):
    """Background sync loop."""
    sync_service = SyncService(settings, SessionLocal())

    if settings.sync_on_startup:
        await sync_service.sync_all_runners()

    while True:
        await asyncio.sleep(settings.sync_interval_seconds)
        try:
            result = await sync_service.sync_all_runners()
            logger.info("sync_completed", **result.to_dict())
        except Exception as e:
            logger.error("sync_failed", error=str(e))
```

### Sync Logic

```python
async def sync_all_runners(self) -> SyncResult:
    # 1. Fetch all runners from GitHub (single API call)
    github_runners = await self.github.list_runners()
    github_by_name = {r.name: r for r in github_runners}

    # 2. Get all non-deleted local runners
    local_runners = self.db.query(Runner).filter(
        Runner.status != "deleted"
    ).all()

    updated = 0
    deleted = 0
    unchanged = 0

    for runner in local_runners:
        github_runner = github_by_name.get(runner.runner_name)

        if github_runner:
            # Runner exists in GitHub - update status
            if self._update_runner_from_github(runner, github_runner):
                updated += 1
            else:
                unchanged += 1
        else:
            # Runner not in GitHub
            if runner.status == "pending":
                # Still pending - check if token expired
                if self._is_token_expired(runner):
                    runner.status = "deleted"
                    runner.deleted_at = utcnow()
                    deleted += 1
                else:
                    unchanged += 1
            else:
                # Was registered, now gone - mark deleted
                runner.status = "deleted"
                runner.deleted_at = utcnow()
                deleted += 1

    self.db.commit()
    return SyncResult(updated=updated, deleted=deleted, unchanged=unchanged)
```

### API Endpoints

Add sync status endpoint to admin API:

```python
@router.get("/sync/status")
async def get_sync_status(admin: AuthenticatedUser = Depends(require_admin)):
    """Get sync service status."""
    return {
        "enabled": settings.sync_enabled,
        "interval_seconds": settings.sync_interval_seconds,
        "last_sync": last_sync_time,
        "next_sync": next_sync_time,
    }

@router.post("/sync/trigger")
async def trigger_sync(admin: AuthenticatedUser = Depends(require_admin)):
    """Manually trigger a sync."""
    result = await sync_service.sync_all_runners()
    return result.to_dict()
```

### Logging

Structured logging for observability:

```python
logger.info("sync_started", runner_count=len(local_runners))
logger.info("sync_completed",
    updated=result.updated,
    deleted=result.deleted,
    unchanged=result.unchanged,
    duration_ms=duration
)
logger.warning("runner_marked_deleted",
    runner_id=runner.id,
    runner_name=runner.runner_name,
    reason="not_found_in_github"
)
```

### Error Handling

```python
async def sync_all_runners(self) -> SyncResult:
    try:
        github_runners = await self.github.list_runners()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            logger.error("sync_rate_limited")
            raise SyncRateLimitedError()
        raise SyncGitHubError(str(e))
    except httpx.RequestError as e:
        logger.error("sync_network_error", error=str(e))
        raise SyncNetworkError(str(e))
```

## Migration Path

1. Add new config options with defaults (no behavior change)
2. Implement SyncService
3. Add background task (disabled by default initially)
4. Add admin API endpoints
5. Update CLI `sync-github` to use SyncService
6. Enable by default after testing

## Testing

1. Unit tests for SyncService logic
2. Integration tests with mock GitHub API
3. Test error handling (rate limits, network errors)
4. Test background task lifecycle

## Label Policy Enforcement

### Enforcement Points

1. **Sync Service (Primary)**
   - On each sync cycle, validates runner labels against user's policy
   - If violation detected:
     - Deletes runner from GitHub via API
     - Marks runner as deleted in local DB
     - Logs security event with severity "high"
   - This is the primary enforcement mechanism

2. **Webhook Handler (Secondary)**
   - Endpoint: `POST /api/v1/webhooks/github`
   - Listens for `workflow_job` events with action `in_progress`
   - Validates runner labels before job executes code
   - Configurable behavior via `LABEL_POLICY_ENFORCEMENT`:
     - `audit`: Log security event only (default)
     - `enforce`: Log event AND cancel the workflow run

### Webhook Setup

To enable webhook enforcement:

1. In GitHub org settings, create a webhook:
   - URL: `https://your-service/api/v1/webhooks/github`
   - Content type: `application/json`
   - Secret: Generate a secure secret
   - Events: Select "Workflow jobs"

2. Configure the service:
   ```bash
   export GITHUB_WEBHOOK_SECRET="your-secret"
   export LABEL_POLICY_ENFORCEMENT="enforce"  # or "audit"
   ```

### Security Events

Policy violations are logged to the `security_events` table:

| Event Type | Description |
|------------|-------------|
| `label_policy_violation` | Runner deleted during sync for label violation |
| `label_policy_violation_workflow` | Violation detected via webhook when job started |

Events include:
- User identity (who provisioned the runner)
- Runner name and GitHub runner ID
- Invalid labels detected
- Action taken (runner_deleted, workflow_cancelled, audit_only)

## Future Enhancements

1. **Metrics**: Prometheus metrics for sync duration, runner counts, violations
2. **Selective Sync**: Sync only runners modified since last sync
3. **Sync Queue**: Queue sync requests to avoid concurrent syncs
4. **Webhook for queued events**: Optionally validate on `queued` action to reject jobs earlier
