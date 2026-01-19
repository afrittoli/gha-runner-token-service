## Label Policy Enforcement

### Overview

The label policy system provides fine-grained access control over runner provisioning by restricting which labels authenticated users may assign to runners. This mechanism prevents unauthorized label usage, enforces organizational boundaries, and maintains runner classification integrity.

### Architecture

The label policy implementation employs a defense-in-depth approach with two enforcement layers:

1. **Validation Layer (Phase 1: Prevention)**: Labels are validated against policy during provisioning request processing, prior to GitHub API interaction
2. **Verification Layer (Phase 2: Detection)**: Labels are verified post-registration via asynchronous GitHub API polling to detect manual configuration tampering

### Policy Components

#### LabelPolicy Entity

```python
{
  "user_identity": "user@example.com",      # OIDC identity to which policy applies
  "allowed_labels": ["team-a", "linux"],    # Explicitly permitted labels
  "label_patterns": ["team-a-.*"],          # Regex patterns for dynamic matching
  "max_runners": 10,                        # Concurrent runner quota
  "require_approval": false,                # Manual approval requirement
  "description": "Team A development",      # Policy documentation
  "created_by": "admin@example.com",        # Policy author
  "created_at": "2026-01-16T12:00:00Z",
  "updated_at": "2026-01-16T12:00:00Z"
}
```

### Enforcement Mechanisms

#### Phase 1: Validation (Prevention)

Label validation occurs during the provisioning request processing pipeline:

**Execution Flow:**

1. Client submits provisioning request with labels
2. Service retrieves applicable label policy for user identity
3. Requested labels are validated against:
   - Explicit allowed label list
   - Regex pattern matches
   - Wildcard permissions (`*`)
4. Policy violation detection:
   - Provisioning request rejected
   - Security event logged
   - Audit trail updated
   - HTTP 400 returned with violation details

**Implementation Location:** `app/services/runner_service.py:provision_runner()`

**Complexity:** O(n×m) where n = requested labels, m = allowed labels + patterns

#### Phase 2: Verification (Detection)

Post-registration verification detects configuration tampering:

**Execution Flow:**

1. Provisioning succeeds, async verification task scheduled (60s delay)
2. Task retrieves runner from GitHub API by ID or name
3. Actual labels compared with expected labels
4. System labels excluded from comparison (self-hosted, OS, architecture)
5. Mismatch detection:
   - Runner immediately deleted from GitHub
   - Security event logged with severity HIGH
   - Local runner status updated to DELETED
   - Audit trail updated

**Implementation Location:** `app/services/runner_service.py:_verify_labels_after_registration()`

**Rationale:** Detects scenarios where runner binary is manually invoked with non-compliant label configuration, bypassing validation layer.

### Security Event Classification

| Event Type | Severity | Trigger Condition | Automated Response |
|------------|----------|-------------------|-------------------|
| `label_policy_violation` (validation) | MEDIUM | Labels fail validation during provisioning | Request rejected |
| `label_policy_violation` (verification) | HIGH | Labels mismatch post-registration | Runner deleted |
| `quota_exceeded` | LOW | User exceeds concurrent runner limit | Request rejected |

### API Operations

#### Create/Update Label Policy

```http
POST /api/v1/admin/label-policies
Authorization: Bearer {ADMIN_TOKEN}
Content-Type: application/json

{
  "user_identity": "alice@example.com",
  "allowed_labels": ["team-a", "linux", "docker"],
  "label_patterns": ["team-a-.*"],
  "max_runners": 10,
  "description": "Team A development runners"
}
```

**Response:**
```json
{
  "user_identity": "alice@example.com",
  "allowed_labels": ["team-a", "linux", "docker"],
  "label_patterns": ["team-a-.*"],
  "max_runners": 10,
  "require_approval": false,
  "description": "Team A development runners",
  "created_by": "admin@example.com",
  "created_at": "2026-01-16T12:00:00Z",
  "updated_at": "2026-01-16T12:00:00Z"
}
```

#### Retrieve Policy

```http
GET /api/v1/admin/label-policies/alice@example.com
Authorization: Bearer {ADMIN_TOKEN}
```

#### List Policies

```http
GET /api/v1/admin/label-policies?limit=100&offset=0
Authorization: Bearer {ADMIN_TOKEN}
```

#### Delete Policy

```http
DELETE /api/v1/admin/label-policies/alice@example.com
Authorization: Bearer {ADMIN_TOKEN}
```

#### Query Security Events

```http
GET /api/v1/admin/security-events?event_type=label_policy_violation&severity=high&limit=100
Authorization: Bearer {ADMIN_TOKEN}
```

**Response:**
```json
{
  "events": [
    {
      "id": 123,
      "event_type": "label_policy_violation",
      "severity": "high",
      "runner_id": "abc-123",
      "runner_name": "worker-001",
      "github_runner_id": 456,
      "user_identity": "alice@example.com",
      "violation_data": {
        "expected_labels": ["team-a"],
        "actual_labels": ["team-a", "gpu"],
        "mismatched_labels": ["gpu"],
        "verification_method": "post_registration"
      },
      "action_taken": "runner_deleted",
      "timestamp": "2026-01-16T12:05:00Z"
    }
  ],
  "total": 1
}
```

### Pattern Matching

Regex patterns enable dynamic label authorization:

**Examples:**

```python
# Team-based namespacing
"team-engineering-.*"  # Matches: team-engineering-backend, team-engineering-frontend

# Environment-based
"(dev|staging|prod)-.*"  # Matches: dev-server, staging-api, prod-worker

# Resource-based
"(gpu|cpu|memory)-.*"  # Matches: gpu-tesla, cpu-optimized, memory-xlarge
```

### Default Behavior

When no policy exists for a user identity:

- **Current Implementation**: Permissive (all labels allowed)
- **Production Recommendation**: Restrictive (no labels allowed, requires explicit policy creation)

Modify `app/services/label_policy_service.py:validate_labels()` to implement restrictive default:

```python
if not policy:
    raise ValueError(f"No label policy configured for user: {user_identity}")
```

### CLI Operations

```bash
# Initialize database schema (includes label policy tables)
python -m app.cli init-db

# List policies
python -m app.cli list-label-policies

# Export security events
python -m app.cli export-security-events --severity high --output violations.json
```

### Integration with OIDC Claims

Label policies may be embedded within OIDC token claims for decentralized policy management:

**OIDC Token Payload:**
```json
{
  "sub": "alice@example.com",
  "email": "alice@example.com",
  "runner_permissions": {
    "allowed_labels": ["team-a", "linux"],
    "label_patterns": ["team-a-.*"],
    "max_runners": 5
  }
}
```

**Implementation:** Extract claims in `app/auth/dependencies.py:get_current_user()` and apply during validation.

**Benefits:**
- Centralized policy management via identity provider
- Real-time policy updates (no database synchronization required)
- Consistent policy enforcement across multiple services

### Database Schema

```sql
-- Label policies table
CREATE TABLE label_policies (
    user_identity VARCHAR PRIMARY KEY,
    allowed_labels TEXT NOT NULL,           -- JSON array
    label_patterns TEXT,                    -- JSON array (nullable)
    max_runners INTEGER,                    -- NULL = unlimited
    require_approval BOOLEAN DEFAULT FALSE,
    description TEXT,
    created_by VARCHAR,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX ix_label_policies_user_identity ON label_policies(user_identity);

-- Security events table
CREATE TABLE security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type VARCHAR NOT NULL,
    severity VARCHAR NOT NULL,
    runner_id VARCHAR,
    runner_name VARCHAR,
    github_runner_id INTEGER,
    user_identity VARCHAR NOT NULL,
    oidc_sub VARCHAR,
    violation_data TEXT NOT NULL,           -- JSON object
    action_taken VARCHAR,
    timestamp TIMESTAMP NOT NULL
);

CREATE INDEX ix_security_events_type_severity ON security_events(event_type, severity);
CREATE INDEX ix_security_events_user_timestamp ON security_events(user_identity, timestamp);
```

### Monitoring and Alerting

**Recommended Metrics:**

- `label_violations_per_hour`: Rate of policy violations
- `label_violations_by_user`: Distribution of violations by user identity
- `label_violations_by_severity`: Distribution by severity level
- `runner_deletion_rate`: Rate of post-registration deletions

**Alert Thresholds:**

- **Warning**: >5 violations per user per day
- **Critical**: >3 high-severity violations per hour (system-wide)

**Integration:**

```python
# Export metrics to Prometheus
from prometheus_client import Counter, Histogram

label_violations = Counter(
    'label_policy_violations_total',
    'Total label policy violations',
    ['user_identity', 'severity']
)

# In label_policy_service.py:log_security_event()
label_violations.labels(
    user_identity=user_identity,
    severity=severity
).inc()
```

### Performance Considerations

**Validation Phase:**
- **Latency**: +5-10ms per provisioning request (local database query)
- **Database Load**: 1 SELECT query per provisioning request
- **Caching**: Policy objects should be cached in production (5-minute TTL)

**Verification Phase:**
- **Latency**: Asynchronous (no impact on provisioning response time)
- **GitHub API Calls**: 1 GET per runner verification (within rate limits)
- **Concurrency**: Verification tasks execute concurrently (asyncio)

**Scalability:**
- Validation scales linearly with provisioning request rate
- Verification scales with runner registration rate (typically lower)
- No synchronous GitHub API calls in critical path

### Security Guarantees

**Threat Model:**

1. **Malicious User**: Attempts to provision runner with unauthorized labels
   - **Mitigation**: Validation layer rejects request before GitHub interaction

2. **Compromised Client**: User bypasses service and registers runner directly
   - **Mitigation**: Not prevented (GitHub registration token already issued)
   - **Note**: Token generation is the trust boundary

3. **Manual Configuration**: User manually configures runner with wrong labels
   - **Mitigation**: Verification layer detects and deletes runner

**Trust Boundaries:**

```
[User] --OIDC Auth--> [Token Service] --Validated--> [GitHub API]
                            |
                       [Label Policy]
                            |
                    [Verification Task] <--Poll-- [GitHub API]
```

**Limitations:**

- Verification occurs post-registration (60-second window of vulnerability)
- Manual runner registration outside service is not prevented
- Relies on GitHub API availability for verification

### Best Practices

1. **Namespace Labels**: Use prefixes to organize labels hierarchically (`team-`, `env-`, `resource-`)
2. **Principle of Least Privilege**: Grant minimum required labels to each user
3. **Regular Audits**: Review security events weekly for emerging patterns
4. **Pattern Caution**: Overly broad regex patterns may inadvertently permit unwanted labels
5. **Quota Configuration**: Set realistic runner quotas to prevent resource exhaustion
6. **Default Deny**: Configure restrictive default behavior in production environments
7. **Policy Versioning**: Document policy changes in `description` field with timestamps
8. **OIDC Integration**: Prefer OIDC claim-based policies for dynamic environments

### Example Policy Configurations

#### Team-Based Isolation

```json
{
  "user_identity": "team-a@example.com",
  "allowed_labels": ["team-a", "linux", "docker"],
  "label_patterns": ["team-a-.*"],
  "max_runners": 10,
  "description": "Team A development isolation"
}
```

#### Environment-Based

```json
{
  "user_identity": "dev-users@example.com",
  "allowed_labels": ["development", "staging"],
  "label_patterns": ["dev-.*", "staging-.*"],
  "max_runners": 20,
  "description": "Non-production environments"
}
```

#### Resource-Based

```json
{
  "user_identity": "ml-team@example.com",
  "allowed_labels": ["gpu", "cuda", "tensorflow", "pytorch"],
  "label_patterns": ["gpu-.*"],
  "max_runners": 5,
  "description": "ML team GPU runners"
}
```

#### Administrative Wildcard

```json
{
  "user_identity": "admin@example.com",
  "allowed_labels": ["*"],
  "max_runners": null,
  "description": "Administrative access"
}
```

### Migration Guide

**Enabling Label Policies for Existing Deployment:**

1. **Database Migration:**
   ```bash
   python -m app.cli init-db  # Creates new tables
   ```

2. **Policy Creation:**
   ```bash
   # Create policies for existing users
   curl -X POST http://localhost:8000/api/v1/admin/label-policies \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "user_identity": "user@example.com",
       "allowed_labels": ["*"],
       "description": "Temporary permissive policy"
     }'
   ```

3. **Gradual Enforcement:**
   - Phase 1: Deploy with permissive defaults (allow all)
   - Phase 2: Create restrictive policies for critical users
   - Phase 3: Monitor security events for violations
   - Phase 4: Enable restrictive defaults globally

4. **Testing:**
   ```bash
   # Test policy validation
   curl -X POST http://localhost:8000/api/v1/runners/provision \
     -H "Authorization: Bearer $USER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "runner_name": "test-runner",
       "labels": ["unauthorized-label"]
     }'
   # Expected: 400 Bad Request with policy violation message
   ```

### Troubleshooting

**Issue:** Policy violation false positives

**Solution:** Verify policy configuration includes all required labels

```bash
curl http://localhost:8000/api/v1/admin/label-policies/user@example.com \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Issue:** Verification task not executing

**Solution:** Verify asyncio event loop is running

```python
# Check logs for:
logger.info("label_verification_passed", ...)  # or
logger.error("label_verification_failed", ...)
```

**Issue:** High-severity violations for legitimate runners

**Solution:** System labels (self-hosted, linux, x64) are automatically excluded. Verify custom labels are in allowed list.

### References

- Label Policy Service Implementation: `app/services/label_policy_service.py`
- Runner Service Integration: `app/services/runner_service.py`
- Admin API Endpoints: `app/api/v1/admin.py`
- Database Models: `app/models.py` (LabelPolicy, SecurityEvent)
- API Schemas: `app/schemas.py`
