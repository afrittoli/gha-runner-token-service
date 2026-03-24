# Backend Architecture

## System Overview

The Runner Token Service (GHARTS) is a secure intermediary that enables third parties to provision GitHub self-hosted runners without exposing privileged credentials.

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
│  │  Database (PostgreSQL)   │  │
│  │  - Runners               │  │
│  │  - Teams                 │  │
│  │  - Audit log             │  │
│  └──────────────────────────┘  │
└─────────┬───────────────────────┘
          │ HTTPS + GitHub App Token
          │
          ▼
┌─────────────────────────┐
│  GitHub API             │
│  - Generate JIT config  │
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
   └─ GitHub generates JIT config (encoded, server-side labels)

4. Token Service → Third Party
   └─ Response: {encoded_jit_config, run_command, expires_at, ...}

5. Third Party → Runner Machine
   └─ Execute: ./run.sh --jitconfig {encoded_jit_config}

6. Runner → GitHub
   └─ Register using JIT config (labels enforced server-side)
   └─ Receive OAuth credentials for long-term use
```

### Token Types

Two authentication paths are supported, distinguished by the `gty` claim in the JWT:

| Path | Detection | Identity | Team resolution |
|------|-----------|----------|-----------------|
| Individual | No `gty` claim | Email/sub from OIDC | DB membership lookup |
| M2M team | `gty=client-credentials` | `m2m:<team-name>` | `OAuthClient` table via `sub` claim |

**Individual tokens** require the user to exist in the `users` table and be active. Team membership is fetched from `user_team_memberships`.

**M2M team tokens** require the Auth0 `client_id` (the token `sub`) to be registered in the `oauth_clients` table and linked to an active team. No per-user DB record is needed.

### Authorization Levels

| Entity | Token Type | Scope | Lifetime |
|--------|-----------|-------|----------|
| Token Service | GitHub App Installation Token | Org-level runner management | 1 hour (auto-refreshed) |
| Third Party (JIT) | JIT Config (via service) | Single runner registration, labels enforced server-side | 1 hour (single-use) |
| Runner | OAuth Token (self-generated) | Runner-specific operations | Until runner deleted |
| Job | Job Token (from GitHub) | Single job execution | Job duration + 10 min |

### Principle of Least Privilege

1. **Token Service**: Holds GitHub App credentials (highest privilege). Never exposed to third parties. Only generates time-limited JIT configs.

2. **Third Parties**: Receive JIT configs with labels already embedded server-side. Cannot override labels. Cannot generate additional tokens. All actions audited with OIDC identity.

3. **Runners**: Self-generate OAuth credentials via RSA keypair. Scoped to own operations only. Cannot access organization management.

## Component Architecture

### API Layer (`app/api/`)

**Responsibilities:**
- HTTP request handling
- Input validation (Pydantic schemas)
- Response formatting
- Error handling

**Endpoints:**
- `POST /api/v1/runners/jit` - Provision runner via JIT config
- `GET /api/v1/runners` - List runners (scoped by user/team)
- `GET /api/v1/runners/{runner_id}` - Get runner status by ID
- `POST /api/v1/runners/{runner_id}/refresh` - Sync status with GitHub
- `DELETE /api/v1/runners/{runner_id}` - Delete runner by ID

### Authentication Layer (`app/auth/`)

**Components:**
- `oidc.py` - OIDC token validation
- `token_types.py` - Token type detection (individual vs M2M)
- `dependencies.py` - FastAPI auth dependencies

**Flow:**
1. Extract Bearer token from Authorization header
2. Detect token type via `gty` claim
3. For M2M: look up `OAuthClient` by `sub`, resolve team
4. For individual: fetch OIDC provider's JWKS, validate signature/issuer/audience/expiration, look up user in DB
5. Return `AuthenticatedUser` object

### GitHub Integration (`app/github/`)

**Components:**
- `app_auth.py` - GitHub App JWT generation and installation token management
- `client.py` - GitHub API operations

**Features:**
- JWT generation for GitHub App authentication
- Installation token caching (refreshed 5 min before expiry)
- JIT config generation (server-side label enforcement)
- Runner listing and status queries
- Runner deletion

### Business Logic (`app/services/`)

**RunnerService** (`runner_service.py`):
- Provision runner via JIT config (validate labels, check quota, call GitHub, create DB record)
- List runners (visibility scoped by user/team)
- Get runner status
- Update runner status (sync with GitHub)
- Deprovision runner (delete from GitHub and DB)
- Audit logging

**LabelPolicyService** (`label_policy_service.py`):
- Validate labels against team policy (`required_labels` + `optional_label_patterns`)
- Check team runner quota (`max_runners`)
- Resolve user's team for provisioning
- Log security events

**TeamService** (`team_service.py`):
- CRUD for teams and team membership
- Runner quota tracking

### Data Layer (`app/models.py`, `app/database.py`)

**Runner:**
- Identity: `id`, `runner_name`, `github_runner_id`
- Configuration: `labels`, `ephemeral` (always true for JIT), `runner_group_id`, `disable_update`
- Ownership: `provisioned_by`, `oidc_sub`
- Team: `team_id`, `team_name` (denormalized)
- State: `status` (pending/active/offline/deleted)
- URL: `github_url`
- Timestamps: `created_at`, `updated_at`, `registered_at`, `deleted_at`

**AuditLog:**
- Event: `event_type`, `runner_id`, `runner_name`, `team_id`
- User: `user_identity`, `oidc_sub`
- Context: `request_ip`, `user_agent`
- Result: `success`, `error_message`
- Data: `event_data` (JSON)

**Team:**
- Identity: `id`, `name`, `description`
- Label policy: `required_labels` (JSON array), `optional_label_patterns` (JSON array of regex)
- Quota: `max_runners` (null = unlimited)
- Status: `is_active`, `deactivation_reason`, `deactivated_at`, `deactivated_by`

**User:**
- Identity: `id`, `email`, `oidc_sub`, `display_name`
- Authorization: `is_admin`, `is_active`, `can_use_jit`

**UserTeamMembership:** Many-to-many between `users` and `teams`.

**OAuthClient:** Maps Auth0 M2M `client_id` → `team_id`. Enables M2M token authentication.

**SecurityEvent:** Records label violations and quota breaches for monitoring.

**GitHubRunnerCache:** Cached snapshot of runners from GitHub API (used by sync worker).

**SyncState:** Single-row table for sync worker leader election and heartbeat.

## Data Flow

### JIT Provisioning Flow

```
┌─────────────┐
│ HTTP POST   │
│ /runners/   │
│ jit         │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ Authenticate     │
│ - Detect token   │
│   type           │
│ - Resolve user   │
│   or team        │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Resolve Team     │
│ - M2M: from JWT  │
│ - Individual:    │
│   membership DB  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Validate Labels  │
│ - required_labels│
│ - optional regex │
│   patterns       │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Check Quota      │
│ (team max_runners│
│  vs active count)│
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Call GitHub API  │
│ POST /jitconfig  │
│ (labels embedded │
│  server-side)    │
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
│ - encoded_jit_   │
│   config         │
│ - run_command    │
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
       │     Set: registered_at (if first time)
       │
       └─ Not found
          ├─ pending → keep pending
          └─ other → mark deleted
```

## Runner State Machine

```
┌─────────┐
│ PENDING │ ← Initial state (JIT config issued)
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
     └─ Runner deleted/ephemeral completes job
        └→ DELETED (terminal state)
```

**State Transitions:**
- `pending` → `active`: Runner successfully registered
- `pending` → `deleted`: Manual deletion
- `active` → `offline`: Runner disconnected
- `active` → `deleted`: Manual deletion or ephemeral job completion
- `offline` → `active`: Runner reconnected
- `offline` → `deleted`: Cleanup or manual deletion

## Label Policy Enforcement

### Team-Based Policy

Label policies are scoped to **teams**, not individual users. Each team defines:

- `required_labels`: Labels that **must** be present in every provisioning request
- `optional_label_patterns`: Regex patterns for additional labels the team is permitted to use
- `max_runners`: Concurrent runner quota (null = unlimited)

System labels (`self-hosted`, OS, architecture) are always allowed and excluded from policy validation.

### Enforcement

Label validation occurs synchronously during the JIT provisioning request, before the GitHub API call. If validation fails, the request is rejected with HTTP 400 and a security event is logged.

**Validation logic:**
1. Filter out system labels
2. Check all `required_labels` are present — reject if any missing
3. For each remaining user label, check it matches at least one `optional_label_patterns` regex — reject if any unmatched

**Security event classification:**

| Event Type | Severity | Trigger | Response |
|------------|----------|---------|----------|
| `label_policy_violation` | MEDIUM | Labels fail validation | Request rejected |
| `quota_exceeded` | LOW | Team exceeds `max_runners` | Request rejected |

### JIT Security Guarantee

Because GHARTS uses the GitHub JIT config API, labels are embedded server-side in the opaque config blob. The runner binary cannot override them at registration time, eliminating the post-registration tampering vector that existed with the legacy registration-token approach.

### Pattern Examples

```python
# Team-based namespacing
"team-engineering-.*"    # Matches: team-engineering-backend, team-engineering-frontend

# Environment-based
"(dev|staging|prod)-.*"  # Matches: dev-server, staging-api, prod-worker

# Resource-based
"(gpu|cpu|memory)-.*"    # Matches: gpu-tesla, cpu-optimized, memory-xlarge
```

### Runner Visibility

| Caller | Sees |
|--------|------|
| Admin | All runners (optionally filtered by team) |
| M2M team token | Only runners belonging to the token's team |
| Individual user | Own runners + all runners for teams they belong to |

## Security Considerations

### Secrets Management

**GitHub App Private Key:**
- Stored as file, path in environment variable
- File permissions: 600 (owner read/write only)
- Never logged or exposed in API

**OIDC Tokens:**
- Validated against provider's JWKS
- Signature, issuer, audience, expiration checked
- Never stored in database

### Audit Trail

All operations logged with:
- Event type (provision_jit, deprovision, etc.)
- User identity (from OIDC)
- Team ID
- Timestamp
- Success/failure
- Event data (sanitized)

### Threat Model

1. **Malicious user — unauthorized labels**: Validation layer rejects provisioning request before GitHub interaction.

2. **Compromised client — bypasses service**: Not prevented at the token-issuance level. The trust boundary is the JIT config generation step.

3. **Manual label tampering post-registration**: Eliminated by JIT provisioning — labels are embedded server-side and cannot be overridden by the runner binary.

**Trust boundary:**
```
[User] --OIDC Auth--> [Token Service] --Validated--> [GitHub API (JIT)]
                            |
                       [Team Policy]
                       (required + optional patterns, quota)
```

## Monitoring & Observability

### Structured Logging

All logs in JSON format via `structlog`:
```json
{
  "event": "request_completed",
  "timestamp": "2026-01-16T12:00:00Z",
  "method": "POST",
  "path": "/api/v1/runners/jit",
  "status_code": 201,
  "user": "alice@example.com"
}
```

### Security Event Metrics

Recommended metrics for alerting:

- `label_violations_per_hour`: Rate of policy violations
- `label_violations_by_user`: Distribution by user identity
- `quota_exceeded_per_team`: Quota breach rate per team
- `m2m_auth_requests_total`: M2M authentication outcomes (success/disabled/not_registered)

**Alert thresholds (recommended):**
- Warning: >5 violations per user per day
- Critical: >3 high-severity violations per hour (system-wide)

### Health Checks

- `/health` endpoint (no auth)
- Database connectivity
- GitHub API reachability
