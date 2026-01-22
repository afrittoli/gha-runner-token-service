# Service Demo Script

Demonstrate the system capabilities and its security and central management and auditing benefits.

## Prerequisites

Before starting the demo, ensure:
- The service is running (see DEVELOPMENT.md or QUICKSTART.md)
- You have the [`docs/scripts/get_oidc_token`](./scripts/oidc.sh) function installed and configured
- Label policies are configured for the users
- The GitHub organization has self-hosted runners enabled

### Environment Variables

```bash
# Service URL
export SERVICE_URL="http://localhost:8000"  # or your deployed URL

# OIDC tokens (obtain from your identity provider)
export ALICE_TOKEN=$(get_oidc_token)
export BOB_TOKEN=$(get_oidc_token)
export ADMIN_TOKEN=$(get_oidc_token)
```

---

## Clean-up

Reset the environment to a known state:

```bash
# Delete all existing runners (admin only)
curl -X POST "$SERVICE_URL/api/v1/admin/batch/delete-runners" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Demo preparation: cleaning up all runners"}'

# Verify no runners exist
curl -s "$SERVICE_URL/api/v1/runners" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.runners'
```

---

## Demonstrate Setup

### Show Dashboard

1. Open the dashboard at `$SERVICE_URL/dashboard`
2. Enter admin token in the "Admin Actions" section
3. Click on the **Users** tab to show pre-provisioned users
4. Click on the **Label Policies** tab to show configured policies
5. Point out the empty Runners table

### List Users (API)

```bash
# List all users
curl -s "$SERVICE_URL/api/v1/admin/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.users[] | {email, is_admin, can_use_jit}'
```

### List Label Policies (API)

```bash
# List all label policies
curl -s "$SERVICE_URL/api/v1/admin/label-policies" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.policies[] | {user_identity, allowed_labels, max_runners}'
```

---

## Provision a Runner

### Attempt with Invalid Labels (Rejected)

```bash
# Alice tries to use unauthorized labels
curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name": "alice-runner-1",
    "labels": ["production", "admin-only"]
  }'

# Expected: 403 Forbidden - labels not permitted by policy
```

### Show Audit Log

```bash
# Check security events for the violation
curl -s "$SERVICE_URL/api/v1/admin/security-events?limit=5" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.events[] | {event_type, severity, user_identity, action_taken}'
```

Also visible in the dashboard under "Security Events" section.

### Provision with Valid Labels (Success)

```bash
# Alice provisions a runner with allowed labels
curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "alice-demo",
    "labels": ["linux", "x64", "team-a"]
  }' | tee /tmp/alice-runner.json | jq

# Save the JIT config for later
export ALICE_JIT_CONFIG=$(jq -r '.encoded_jit_config' /tmp/alice-runner.json)
export ALICE_RUNNER_NAME=$(jq -r '.runner_name' /tmp/alice-runner.json)
```

### Explain System Labels

The response shows the full label list including system labels:
- `self-hosted`: Required for all self-hosted runners
- `Linux`/`macOS`/`Windows`: OS label (auto-detected or specified)
- `X64`/`ARM64`: Architecture label

These are automatically added by the service - users cannot bypass them.

### Show JIT Config Content

```bash
# The JIT config is a base64-encoded JSON structure
echo $ALICE_JIT_CONFIG | base64 -d | jq

# Contains:
# - encoded credentials
# - runner name
# - labels (enforced by GitHub, cannot be changed)
# - runner group ID
```

### Start the Runner

```bash
# On the runner machine (or container):
cd /path/to/actions-runner

# Start using JIT config (no ./config.sh needed!)
./run.sh --jitconfig "$ALICE_JIT_CONFIG"
```

### Show Runner in GitHub UI

1. Navigate to GitHub Organization → Settings → Actions → Runners
2. Point out the new runner with correct labels
3. Show it's in the correct runner group

### Show Runner in Dashboard

1. Refresh the dashboard
2. Show the runner in the Runners table
3. Point out the status change from "pending" → "online"
4. Explain the automatic sync:
   - Runs every 60 seconds (configurable)
   - Updates status from GitHub
   - Detects deleted/orphaned runners

---

## Demo Label Change Prevention

### Can JIT Credentials Modify Labels?

**No.** JIT (Just-In-Time) provisioning enforces labels server-side. Unlike registration tokens:
- Labels are embedded in the JIT config by GitHub
- The runner cannot modify them during startup
- Any attempt to use different labels will fail

### Alternative: Registration Token Approach

With registration tokens (not recommended), users could theoretically:
1. Get a registration token
2. Run `./config.sh` with different labels

The sync service detects this:

```bash
# Trigger a sync to detect label changes
curl -X POST "$SERVICE_URL/api/v1/admin/sync/trigger" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# If label drift detected, runner is deleted and logged
curl -s "$SERVICE_URL/api/v1/admin/security-events?event_type=label_drift_detected" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.events[0]'
```

---

## Demo Multi-User

### Provision Runner for Bob

```bash
# Bob provisions his own runner
curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $BOB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "bob-demo",
    "labels": ["linux", "x64", "team-b"]
  }' | tee /tmp/bob-runner.json | jq

export BOB_RUNNER_ID=$(jq -r '.runner_id' /tmp/bob-runner.json)
```

### Show All Runners (Admin Dashboard)

1. Refresh the dashboard
2. Both Alice's and Bob's runners visible
3. Filter by status or search by name

### List Runners per User (API)

```bash
# Alice can only see her runners
curl -s "$SERVICE_URL/api/v1/runners" \
  -H "Authorization: Bearer $ALICE_TOKEN" | jq '.runners[] | {runner_name, provisioned_by}'

# Bob can only see his runners
curl -s "$SERVICE_URL/api/v1/runners" \
  -H "Authorization: Bearer $BOB_TOKEN" | jq '.runners[] | {runner_name, provisioned_by}'

# Admin sees all runners
curl -s "$SERVICE_URL/api/v1/admin/batch/delete-runners" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Listing only"}' 2>/dev/null || \
  curl -s "$SERVICE_URL/api/v1/runners" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.runners[] | {runner_name, provisioned_by}'
```

### Bob Tries to Delete Alice's Runner (Failed)

```bash
export ALICE_RUNNER_ID=$(jq -r '.runner_id' /tmp/alice-runner.json)

# Bob tries to delete Alice's runner - should fail
curl -X DELETE "$SERVICE_URL/api/v1/runners/$ALICE_RUNNER_ID" \
  -H "Authorization: Bearer $BOB_TOKEN"

# Expected: 404 Not Found (runner not visible to Bob)
```

### Bob Deletes His Own Runner (Success)

```bash
# Bob can delete his own runner
curl -X DELETE "$SERVICE_URL/api/v1/runners/$BOB_RUNNER_ID" \
  -H "Authorization: Bearer $BOB_TOKEN" | jq
```

### Bob Tries to Use Alice's Runner Number (Failed)

```bash
# Bob tries to provision a runner with same name as Alice's
curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $BOB_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"runner_name\": \"$ALICE_RUNNER_NAME\",
    \"labels\": [\"linux\", \"x64\", \"team-b\"]
  }"

# Expected: 400 Bad Request - runner name already exists
```

### Bob Steals Alice's JIT Config (Failed)

```bash
# Bob tries to use Alice's JIT config
# On runner machine:
./run.sh --jitconfig "$ALICE_JIT_CONFIG"

# Expected: Fails - JIT config can only be used once and is tied to the runner name
# GitHub rejects reuse of JIT configs
```

### Runner Group Isolation

Explain how `runner_group_id` can be used:
- Different runner groups for different teams
- Workflows specify which group to use
- Prevents cross-team access to runners

### Bob Provisions a New Runner

```bash
# Bob provisions a fresh runner
curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $BOB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "bob-new",
    "labels": ["linux", "x64", "team-b"]
  }' | jq
```

---

## Demo Ephemeral Runners

### Trigger a Workflow

Use the demo workflow (requires runner to be started):

1. Go to GitHub repository → Actions → "Demo Ephemeral Runner"
2. Click "Run workflow"
3. Enter runner labels: `self-hosted,linux,x64,team-a` (matching Alice's runner)
4. Click "Run workflow"

Or via CLI:

```bash
gh workflow run demo-ephemeral.yaml \
  --field runner_labels="self-hosted,linux,team-a" \
  --field message="Demo ephemeral runner!"
```

### Watch the Job Run

1. Observe the workflow starting
2. Job picks up on Alice's runner
3. Workflow completes

### Show Runner Auto-Deletion

```bash
# Wait for sync (or trigger manually)
curl -X POST "$SERVICE_URL/api/v1/admin/sync/trigger" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Check runner status - should be "deleted"
curl -s "$SERVICE_URL/api/v1/runners" \
  -H "Authorization: Bearer $ALICE_TOKEN" | jq '.runners[] | {runner_name, status}'
```

### Show Audit Log

```bash
# View recent events
curl -s "$SERVICE_URL/api/v1/admin/security-events?limit=10" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.events[] | {event_type, runner_name, action_taken, timestamp}'
```

---

## Demo Admin Capabilities

### Provision Multiple Runners

```bash
# Alice provisions a few runners (not started)
for i in 1 2 3; do
  curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
    -H "Authorization: Bearer $ALICE_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"runner_name_prefix\": \"alice-batch-$i\", \"labels\": [\"linux\", \"team-a\"]}"
done

# Bob provisions a few runners (not started)
for i in 1 2; do
  curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
    -H "Authorization: Bearer $BOB_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"runner_name_prefix\": \"bob-batch-$i\", \"labels\": [\"linux\", \"team-b\"]}"
done
```

### Alter Label Policy

```bash
# Update Alice's label policy to add more allowed labels
curl -X POST "$SERVICE_URL/api/v1/admin/label-policies" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_identity": "alice@example.com",
    "allowed_labels": ["linux", "x64", "team-a", "gpu"],
    "max_runners": 10,
    "description": "Team A runners with GPU support"
  }' | jq
```

### Add a New User

```bash
# Create a new user
curl -X POST "$SERVICE_URL/api/v1/admin/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "charlie@example.com",
    "display_name": "Charlie",
    "is_admin": false,
    "can_use_registration_token": false,
    "can_use_jit": true
  }' | jq
```

### Disable a User

```bash
# Disable a specific user (soft delete)
export CHARLIE_ID=$(curl -s "$SERVICE_URL/api/v1/admin/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.users[] | select(.email=="charlie@example.com") | .id')

curl -X DELETE "$SERVICE_URL/api/v1/admin/users/$CHARLIE_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Charlie can no longer authenticate
```

### Disable All Users (Emergency)

```bash
# Security incident: disable all non-admin users
curl -X POST "$SERVICE_URL/api/v1/admin/batch/disable-users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Security incident: suspending all user access pending investigation",
    "exclude_admins": true
  }' | jq
```

### Restore All Users

```bash
# Incident resolved: restore all users
curl -X POST "$SERVICE_URL/api/v1/admin/batch/restore-users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Security incident resolved: restoring normal access"
  }' | jq
```

### Delete a Single Runner

```bash
# Admin deletes a specific runner
curl -X POST "$SERVICE_URL/api/v1/admin/batch/delete-runners" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Cleanup: removing stale test runner",
    "runner_ids": ["<runner-id>"]
  }' | jq
```

### Delete All Runners for a User

```bash
# Delete all runners for a terminated employee
curl -X POST "$SERVICE_URL/api/v1/admin/batch/delete-runners" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Termination: removing all runners for alice@example.com",
    "user_identity": "alice@example.com"
  }' | jq
```

### Delete All Runners

```bash
# Emergency: delete all runners
curl -X POST "$SERVICE_URL/api/v1/admin/batch/delete-runners" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Emergency cleanup: removing all runners due to security incident"
  }' | jq
```

### View Complete Audit Trail

```bash
# All security events
curl -s "$SERVICE_URL/api/v1/admin/security-events?limit=50" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.events[] | {timestamp, event_type, severity, user_identity, action_taken}'

# Filter by type
curl -s "$SERVICE_URL/api/v1/admin/security-events?event_type=batch_disable_users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Filter by severity
curl -s "$SERVICE_URL/api/v1/admin/security-events?severity=high" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

Dashboard also shows security events in the "Security Events" section with filtering options.

---

## Summary

Key security benefits demonstrated:

1. **Label Enforcement**: JIT provisioning enforces labels server-side
2. **User Isolation**: Users can only see/manage their own runners
3. **Audit Trail**: All actions logged for compliance
4. **Central Management**: Admins can manage all runners from one place
5. **Emergency Controls**: Batch disable/delete for incident response
6. **Ephemeral by Default**: Runners auto-delete after one job
