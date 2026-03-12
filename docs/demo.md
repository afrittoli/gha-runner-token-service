# Service Demo Script

Demonstrate the system capabilities and its security and central management and auditing benefits.

## Prerequisites

Before starting the demo, ensure:
- The service is running (see development.md or quickstart.md)
- You have the [`docs/scripts/oidc.sh`](./scripts/oidc.sh) function installed and configured
- Source the CLI credentials `source docs/.cli.env`
- Teams are configured with users and runner policies
- The GitHub organization has self-hosted runners enabled
- Alias `alias curl="curl -sw '%{stderr}Response: %{http_code}\n'"`

### Environment Variables

Copy `docs/.cli.env.example` to `docs/.cli.env` and fill in your Auth0 credentials.

```bash
# Service URL
export SERVICE_URL="http://localhost:8000"  # or your deployed URL
export DASHBOARD_URL="http://localhost:8080/app/"

# Source the CLI environment (Auth0 credentials for token acquisition)
source docs/.cli.env

# Individual OIDC tokens (device flow — opens browser for login)
source docs/scripts/oidc.sh
export ALICE_TOKEN=$(get_oidc_token)
export BOB_TOKEN=$(get_oidc_token)
export ADMIN_TOKEN=$(get_oidc_token)

# M2M token for CI/CD pipeline demo (client credentials flow — no browser needed)
export M2M_TOKEN=$(curl -s --request POST \
  --url "https://${AUTH0_DOMAIN}/oauth/token" \
  --header "content-type: application/json" \
  --data "{
    \"client_id\": \"${AUTH0_M2M_CLIENT_ID}\",
    \"client_secret\": \"${AUTH0_M2M_CLIENT_SECRET}\",
    \"audience\": \"${AUTH0_AUDIENCE}\",
    \"grant_type\": \"client_credentials\"
  }" | jq -r '.access_token')
```

---

## Clean-up

Reset the environment to a known state:

```bash
# Delete all existing runners (admin only)
curl -X POST "$SERVICE_URL/api/v1/admin/batch/delete-runners" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Demo preparation: cleaning up all runners"}' | jq .

# Verify no runners exist
curl -s "$SERVICE_URL/api/v1/runners" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.runners'
```

---

## Demonstrate Setup

### Show Dashboard

1. Open the dashboard at `$DASHBOARD_URL/dashboard`
2. Click on the **Users** tab to show pre-provisioned users
3. Click on the **Teams** tab to show configured teams and their runner policies
4. Point out the empty Runners table

### List Users (API)

```bash
# List all users
curl -s "$SERVICE_URL/api/v1/admin/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.users[] | {email, is_admin, can_use_jit}'
```

### List Teams (API)

```bash
# List all teams (each team defines runner policies: required_labels, max_runners)
curl -s "$SERVICE_URL/api/v1/admin/teams" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.teams[] | {name, required_labels, max_runners, member_count}'
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
    "runner_name_prefix": "alice-runner",
    "labels": ["linux", "arm64", "secretsauce"]
  }'

# Expected: 403 Forbidden - labels not permitted by policy
```

### Show the Security Log

```bash
# Check security events for the violation
curl -s "$SERVICE_URL/api/v1/admin/security-events?limit=1" \
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
    "labels": ["linux", "arm64", "alice"]
  }' | tee /tmp/alice-runner.json | jq '.encoded_jit_config = (.encoded_jit_config[:20] + "...") | .run_command = (.run_command[:20] + "...")'

# Save the JIT config for later
export ALICE_JIT_CONFIG=$(jq -r '.encoded_jit_config' /tmp/alice-runner.json)
```

### Show JIT Config Content

```bash
# The JIT config is a base64-encoded JSON structure, runner details, credentials

# Runner:
echo $ALICE_JIT_CONFIG | base64 -d | jq -r '.[".runner"]' | base64 -D | jq .

# Mention the labels

### Explain System Labels

The response shows the full label list including system labels:
- `self-hosted`: Required for all self-hosted runners


### Start the Runner

```bash
# On the runner machine (or container):
export ALICE_JIT_CONFIG=$(jq -r '.encoded_jit_config' /tmp/alice-runner.json)

podman run -it --rm \
  ghcr.io/actions/actions-runner:latest \
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

### Bob Steals Alice's JIT Config (Failed)


```bash
# On the runner machine (or container):
export ALICE_JIT_CONFIG=$(jq -r '.encoded_jit_config' /tmp/alice-runner.json)

podman run -it --rm \
  ghcr.io/actions/actions-runner:latest \
  ./run.sh --jitconfig "$ALICE_JIT_CONFIG"
```

Run a job to consume the first runner.
Bob's attempt fails.

---

## Demo Label Change Prevention

### Can JIT Credentials Modify Labels?

**No.** JIT (Just-In-Time) provisioning enforces labels server-side. Unlike registration tokens:
- Labels are embedded in the JIT config by GitHub
- The runner cannot modify them during startup
- Any attempt to use different labels will fail

---

## Demo Multi-User

### Provision Runner for Alice

```bash
curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $ALICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "alice-demo",
    "labels": ["linux", "arm64", "alice"]
  }' | tee /tmp/alice-runner.json | jq '.encoded_jit_config = (.encoded_jit_config[:20] + "...") | .run_command = (.run_command[:20] + "...")'
```

# Save the JIT config for later

```bash
export ALICE_JIT_CONFIG=$(jq -r '.encoded_jit_config' /tmp/alice-runner.json)
export ALICE_RUNNER_NAME=$(jq -r '.runner_name' /tmp/alice-runner.json)
```

### Provision Runner for Bob

```bash
# Bob provisions his own runner
curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $BOB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "bob-demo",
    "labels": ["linux", "arm64", "bob"]
  }' | tee /tmp/bob-runner.json | jq '.encoded_jit_config = (.encoded_jit_config[:20] + "...") | .run_command = (.run_command[:20] + "...")'

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
    \"labels\": [\"linux\", \"arm64\", \"bob\"]
  }"

# Expected: 400 Bad Request - runner name already exists
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
    "labels": ["linux", "arm64", "bob"]
  }' | tee /tmp/bob-runner.json | jq '.encoded_jit_config = (.encoded_jit_config[:20] + "...") | .run_command = (.run_command[:20] + "...")'

export BOB_JIT_CONFIG=$(jq -r '.encoded_jit_config' /tmp/bob-runner.json)
```

### Bob Starts the Runner

```bash
# On the runner machine (or container):
podman run -it --rm \
  ghcr.io/actions/actions-runner:latest \
  ./run.sh --jitconfig "$BOB_JIT_CONFIG"
```

---

## Demo Ephemeral Runners

### Trigger a Workflow

Use the demo workflow (requires runner to be started):

1. Go to GitHub repository → Actions → "Hello for Bob"
2. Click "Run workflow"

Or via CLI:

### Watch the Job Run

1. Observe the workflow starting
2. Job picks up on Bob's runner
3. Workflow completes

### Show Runner Auto-Deletion

```bash
# Wait for sync (or trigger manually)
curl -X POST "$SERVICE_URL/api/v1/admin/sync/trigger" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Check runner status - should be "deleted"
curl -s "$SERVICE_URL/api/v1/runners" \
  -H "Authorization: Bearer $BOB_TOKEN" | jq '.runners[] | {runner_name, status}'
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
    -d "{\"runner_name_prefix\": \"alice-batch-$i\", \"labels\": [\"linux\", \"alice\"]}" | jq '.encoded_jit_config = (.encoded_jit_config[:20] + "...") | .run_command = (.run_command[:20] + "...")'
done

# Bob provisions a few runners (not started)
for i in 1 2; do
  curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
    -H "Authorization: Bearer $BOB_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"runner_name_prefix\": \"bob-batch-$i\", \"labels\": [\"linux\", \"bob\"]}" | jq '.encoded_jit_config = (.encoded_jit_config[:20] + "...") | .run_command = (.run_command[:20] + "...")'
done
```

### Admin Console

Show GitHub App config

### Update Team Runner Policy

```bash
# Update a team's runner policy (allowed labels and runner limit)
export ALICE_TEAM_ID=$(curl -s "$SERVICE_URL/api/v1/admin/teams" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.teams[] | select(.name=="alice") | .id')

curl -X PUT "$SERVICE_URL/api/v1/admin/teams/$ALICE_TEAM_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "required_labels": ["linux", "arm64", "alice", "gpu"],
    "max_runners": 10
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
    "can_use_jit": true
  }' | jq
```

### Disable a User

Disable Alice via dashboard.
Try to provision a runner.

```bash
# Disable a specific user (soft delete)
export CHARLIE_ID=$(curl -s "$SERVICE_URL/api/v1/admin/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.users[] | select(.email=="charlie@example.com") | .id')

curl -X DELETE "$SERVICE_URL/api/v1/admin/users/$CHARLIE_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Charlie can no longer authenticate
```

### Disable All Users (Emergency)

Disable all users. Note how explanation is noted.

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

Note how a reason is needed

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

### View Security Events


---

## Demo M2M (Machine-to-Machine) Authentication

Demonstrate how CI/CD pipelines provision runners without human login using OAuth `client_credentials` grant.

### Register M2M Client (Admin)

Before a pipeline can use M2M authentication, an admin registers its Auth0 client_id for a team:

```bash
# First create a team (if not already existing)
curl -X POST "$SERVICE_URL/api/v1/admin/teams" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "platform-team",
    "description": "Platform engineering team"
  }' | jq

export TEAM_ID=$(curl -s "$SERVICE_URL/api/v1/admin/teams" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.teams[] | select(.name=="platform-team") | .id')

# Register the M2M client for the team
curl -X POST "$SERVICE_URL/api/v1/admin/oauth-clients" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"client_id\": \"${AUTH0_M2M_CLIENT_ID}\",
    \"team_id\": \"${TEAM_ID}\",
    \"description\": \"Platform team CI/CD pipeline\"
  }" | jq
```

### Obtain M2M Token (Pipeline simulation)

```bash
# The pipeline obtains a token using client_credentials — no human interaction
export M2M_TOKEN=$(curl -s --request POST \
  --url "https://${AUTH0_DOMAIN}/oauth/token" \
  --header "content-type: application/json" \
  --data "{
    \"client_id\": \"${AUTH0_M2M_CLIENT_ID}\",
    \"client_secret\": \"${AUTH0_M2M_CLIENT_SECRET}\",
    \"audience\": \"${AUTH0_AUDIENCE}\",
    \"grant_type\": \"client_credentials\"
  }" | jq -r '.access_token')

# Show the token claims (note the "team" claim injected by Auth0 Action)
echo $M2M_TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq '{sub, team, iss, exp}'
```

### Provision Runner via M2M Token

```bash
# Pipeline provisions a runner using the M2M token
curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $M2M_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "pipeline-runner",
    "labels": ["linux", "arm64"]
  }' | tee /tmp/m2m-runner.json | jq '.encoded_jit_config = (.encoded_jit_config[:20] + "...") | .run_command = (.run_command[:20] + "...")'
```

### Show Team Isolation

```bash
# M2M token can only see runners provisioned by its team
curl -s "$SERVICE_URL/api/v1/runners" \
  -H "Authorization: Bearer $M2M_TOKEN" | jq '.runners[] | {runner_name, provisioned_by}'

# Admin sees all runners including M2M-provisioned ones
curl -s "$SERVICE_URL/api/v1/runners" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.runners[] | {runner_name, provisioned_by}'
```

### List Registered M2M Clients (Admin)

```bash
curl -s "$SERVICE_URL/api/v1/admin/oauth-clients" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.clients[] | {client_id, team_id, description, last_used_at}'
```

### Revoke M2M Client (Admin)

```bash
export CLIENT_UUID=$(curl -s "$SERVICE_URL/api/v1/admin/oauth-clients" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r ".clients[] | select(.client_id==\"${AUTH0_M2M_CLIENT_ID}\") | .id")

# Disable the client (pipeline can no longer authenticate)
curl -X PATCH "$SERVICE_URL/api/v1/admin/oauth-clients/$CLIENT_UUID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}' | jq

# Attempt to use the disabled token — should now fail with 403
curl -X POST "$SERVICE_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $M2M_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"runner_name_prefix": "blocked-runner", "labels": ["linux"]}' | jq
```

---

## Summary

Key security benefits demonstrated:

1. **Team-based Policy Enforcement**: JIT provisioning enforces labels and runner limits per team
2. **User Isolation**: Users can only see/manage their own runners
3. **Audit Trail**: All actions logged for compliance
4. **Central Management**: Admins can manage all runners from one place
5. **Emergency Controls**: Batch disable/delete for incident response
6. **Ephemeral by Default**: Runners auto-delete after one job
7. **M2M Authentication**: CI/CD pipelines authenticate without human login using `client_credentials` grant; admins can revoke access instantly
