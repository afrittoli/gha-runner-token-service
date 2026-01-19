# Architecture Documentation

## System Overview

The Runner Token Service is a secure intermediary that enables third parties to provision GitHub self-hosted runners without exposing privileged credentials.

```
┌─────────────────┐
│  Third Party    │
│  (OIDC Auth)    │
└────────┬────────┘
         │ HTTPS + Bearer Token
         │
         ▼
┌─────────────────────────────────┐
│   Runner Token Service          │
│                                 │
│  ┌──────────────────────────┐  │
│  │  FastAPI Application     │  │
│  │  - REST API              │  │
│  │  - OIDC Validation       │  │
│  │  - Audit Logging         │  │
│  └──────────┬───────────────┘  │
│             │                   │
│  ┌──────────▼───────────────┐  │
│  │  Business Logic          │  │
│  │  - Runner provisioning   │  │
│  │  - State management      │  │
│  │  - GitHub API calls      │  │
│  └──────────┬───────────────┘  │
│             │                   │
│  ┌──────────▼───────────────┐  │
│  │  Database (SQLite)       │  │
│  │  - Runners               │  │
│  │  - Audit log             │  │
│  └──────────────────────────┘  │
└─────────┬───────────────────────┘
          │ HTTPS + GitHub App Token
          │
          ▼
┌─────────────────────────┐
│  GitHub API             │
│  - Generate tokens      │
│  - List/delete runners  │
└─────────────────────────┘
          │
          │ Runner registers
          │
          ▼
┌─────────────────────────┐
│  GitHub Actions Service │
│  - Runner registration  │
│  - Job assignment       │
└─────────────────────────┘
```

## Security Architecture

### Authentication Flow

```
1. Third Party → OIDC Provider
   └─ Obtain OIDC token (JWT)

2. Third Party → Token Service
   └─ Request: Bearer {OIDC_TOKEN}
   └─ Service validates token against OIDC provider's JWKS

3. Token Service → GitHub API
   └─ Request: Bearer {GITHUB_APP_INSTALLATION_TOKEN}
   └─ GitHub generates registration token

4. Token Service → Third Party
   └─ Response: {registration_token, expires_at, ...}

5. Third Party → Runner Machine
   └─ Configure runner with registration token

6. Runner → GitHub
   └─ Register using token, generate RSA keypair
   └─ Receive OAuth credentials for long-term use
```

### Authorization Levels

| Entity | Token Type | Scope | Lifetime |
|--------|-----------|-------|----------|
| Token Service | GitHub App Installation Token | Org-level runner management | 1 hour (auto-refreshed) |
| Third Party | Registration Token (via service) | Single runner registration | 1 hour (single-use) |
| Runner | OAuth Token (self-generated) | Runner-specific operations | Until runner deleted |
| Job | Job Token (from GitHub) | Single job execution | Job duration + 10 min |

### Principle of Least Privilege

1. **Token Service**:
   - Holds GitHub App credentials (highest privilege)
   - Never exposed to third parties
   - Only generates time-limited registration tokens

2. **Third Parties**:
   - Receive time-limited registration tokens
   - Cannot access other runners
   - Cannot generate additional tokens
   - All actions audited with OIDC identity

3. **Runners**:
   - Self-generate OAuth credentials via RSA keypair
   - Scoped to own operations only
   - Cannot access organization management

## Component Architecture

### API Layer (`app/api/`)

**Responsibilities:**
- HTTP request handling
- Input validation (Pydantic schemas)
- Response formatting
- Error handling

**Endpoints:**
- `POST /api/v1/runners/provision` - Generate registration token
- `GET /api/v1/runners` - List user's runners
- `GET /api/v1/runners/{runner_id}` - Get runner status by ID
- `POST /api/v1/runners/{runner_id}/refresh` - Sync with GitHub
- `DELETE /api/v1/runners/{runner_id}` - Delete runner by ID

### Authentication Layer (`app/auth/`)

**Components:**
- `oidc.py` - OIDC token validation
- `dependencies.py` - FastAPI auth dependencies

**Flow:**
1. Extract Bearer token from Authorization header
2. Fetch OIDC provider's JWKS
3. Validate token signature, issuer, audience, expiration
4. Extract user identity (email/sub)
5. Return `AuthenticatedUser` object

### GitHub Integration (`app/github/`)

**Components:**
- `app_auth.py` - GitHub App JWT generation and installation token management
- `client.py` - GitHub API operations

**Features:**
- JWT generation for GitHub App authentication
- Installation token caching (refreshed 5 min before expiry)
- Runner registration token generation
- Runner removal token generation
- Runner listing and status queries
- Runner deletion

### Business Logic (`app/services/`)

**RunnerService:**
- Provision runner (generate token, create DB record)
- List runners (filter by user)
- Get runner status
- Update runner status (sync with GitHub)
- Deprovision runner (delete from GitHub and DB)
- Audit logging

### Data Layer (`app/models.py`, `app/database.py`)

**Models:**

**Runner:**
- Identity: id, runner_name, github_runner_id
- Configuration: labels, ephemeral, runner_group_id
- Ownership: provisioned_by, oidc_sub
- State: status (pending/active/offline/deleted)
- Tokens: registration_token (cleared after use)
- Timestamps: created_at, registered_at, deleted_at

**AuditLog:**
- Event: event_type, runner_id, runner_name
- User: user_identity, oidc_sub
- Context: request_ip, user_agent
- Result: success, error_message
- Data: event_data (JSON)

**GitHubRunnerCache:**
- Cached GitHub API data
- Used for status syncing

## Data Flow

### Provisioning Flow

```
┌─────────────┐
│ HTTP POST   │
│ /provision  │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ Validate Request │
│ - runner_name    │
│ - labels         │
│ - ephemeral      │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Check Existing   │
│ (DB query)       │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Generate GitHub  │
│ App JWT          │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Get Installation │
│ Token (cached)   │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Call GitHub API  │
│ POST /runners/   │
│ registration-    │
│ token            │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Create Runner    │
│ Record in DB     │
│ (status=pending) │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Log Audit Event  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Return Response  │
│ - token          │
│ - config cmd     │
└──────────────────┘
```

### Status Update Flow

```
┌─────────────┐
│ Refresh     │
│ Request     │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ Get Local Runner │
│ (DB query)       │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Query GitHub API │
│ GET /runners     │
│ ?name={name}     │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Compare State    │
└──────┬───────────┘
       │
       ├─ Found in GitHub
       │  └─ Update: github_runner_id, status
       │     Clear: registration_token
       │     Set: registered_at (if first time)
       │
       └─ Not found
          ├─ pending → keep pending
          └─ other → mark deleted
```

## State Machine

### Runner States

```
┌─────────┐
│ PENDING │ ← Initial state (token issued)
└────┬────┘
     │
     │ Runner registers with GitHub
     │
     ▼
┌─────────┐
│ ACTIVE  │ ← Runner online, accepting jobs
└────┬────┘
     │
     ├─ Runner offline temporarily
     │  └→ OFFLINE
     │
     └─ Runner deleted/ephemeral
        └→ DELETED (terminal state)
```

**State Transitions:**
- `pending` → `active`: Runner successfully registered
- `pending` → `deleted`: Registration timeout or manual deletion
- `active` → `offline`: Runner disconnected
- `active` → `deleted`: Manual deletion or ephemeral cleanup
- `offline` → `active`: Runner reconnected
- `offline` → `deleted`: Cleanup or manual deletion

## Security Considerations

### Secrets Management

**GitHub App Private Key:**
- Stored as file, path in environment variable
- File permissions: 600 (owner read/write only)
- Never logged or exposed in API

**Registration Tokens:**
- Time-limited (1 hour)
- Single-use (cleared from DB after registration)
- Masked in logs via secret masker

**OIDC Tokens:**
- Validated against provider's JWKS
- Signature, issuer, audience, expiration checked
- Never stored in database

### Audit Trail

All operations logged with:
- Event type (provision, deprovision, etc.)
- User identity (from OIDC)
- Timestamp
- Success/failure
- IP address (optional)
- Event data (sanitized)

### Rate Limiting

GitHub API rate limits:
- 60 requests/hour per installation (authentication endpoint)
- 5000 requests/hour per installation (general API)

Service should implement:
- Token caching (installation tokens)
- Backoff on rate limit errors
- Queue for bulk operations

## Scalability

### Current Architecture (SQLite)

**Suitable for:**
- Small to medium deployments (< 1000 runners)
- Single instance deployment
- Development and testing

**Limitations:**
- No horizontal scaling (single writer)
- Local file storage

### Production Architecture (PostgreSQL)

**Recommended:**
```
DATABASE_URL=postgresql://user:pass@host:5432/runners
```

**Benefits:**
- Horizontal scaling (multiple API instances)
- Connection pooling
- Better concurrent write performance
- Backup and replication support

### Caching

**Installation Token Cache:**
- In-memory cache per instance
- 1-hour TTL (refreshed 5 min before expiry)
- Reduces GitHub API calls

**Future Enhancements:**
- Redis for shared cache across instances
- Runner status cache (reduce GitHub API queries)

## Deployment Patterns

### Single Instance (Development)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Multi-Worker (Production)

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker

```bash
docker build -t runner-token-service .
docker run -p 8000:8000 \
  -e GITHUB_APP_ID=... \
  -v ./github-app-private-key.pem:/app/github-app-private-key.pem:ro \
  runner-token-service
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: runner-token-service
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: runner-token-service:latest
        env:
        - name: DATABASE_URL
          value: postgresql://...
        - name: GITHUB_APP_PRIVATE_KEY_PATH
          value: /secrets/github-app-key.pem
        volumeMounts:
        - name: github-app-key
          mountPath: /secrets
          readOnly: true
      volumes:
      - name: github-app-key
        secret:
          secretName: github-app-key
```

## Monitoring & Observability

### Structured Logging

All logs in JSON format:
```json
{
  "event": "request_completed",
  "timestamp": "2026-01-16T12:00:00Z",
  "method": "POST",
  "path": "/api/v1/runners/provision",
  "status_code": 201,
  "user": "alice@example.com"
}
```

### Metrics (Recommended)

- Runner provisioning rate
- Registration success/failure rate
- GitHub API latency
- Database query latency
- Active runners count
- Ephemeral vs persistent ratio

### Health Checks

- `/health` endpoint (no auth)
- Database connectivity
- GitHub API reachability

## Future Enhancements

1. **Webhooks**: Receive GitHub events for runner status changes
2. **Quotas**: Per-user runner limits
3. **Runner Pools**: Group management
4. **Auto-scaling**: Dynamic runner provisioning based on job queue
5. **Multi-org Support**: Manage runners across multiple organizations
6. **UI Dashboard**: Web interface for runner management
7. **Metrics Export**: Prometheus endpoint
8. **Runner Templates**: Pre-configured runner profiles
