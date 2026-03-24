# GHARTS End-User Guide

**GHARTS** (GitHub Actions Runner Token Service) is a secure central service that lets you provision GitHub self-hosted runners using your existing identity credentials — no GitHub App keys, no PATs, no shared secrets.

## Table of Contents

- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Obtaining credentials](#obtaining-credentials)
  - [Individual user (OIDC)](#individual-user-oidc)
  - [Automated pipelines (M2M)](#automated-pipelines-m2m)
- [Provisioning runners](#provisioning-runners)
  - [JIT provisioning](#jit-provisioning)
- [Runner management](#runner-management)
  - [List runners](#list-runners)
  - [Refresh runner status](#refresh-runner-status)
  - [Deprovision a runner](#deprovision-a-runner)
- [Teams and label policies](#teams-and-label-policies)
- [Using the dashboard](#using-the-dashboard)
- [Troubleshooting](#troubleshooting)

---

## Quick start

You need: the GHARTS service URL and an OIDC token (ask your administrator).

```bash
export GHARTS_URL="https://gharts.example.com"
export GHARTS_TOKEN="<your-oidc-jwt>"

# Provision a JIT runner
RESPONSE=$(curl -s -X POST "$GHARTS_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $GHARTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "my-runner",
    "labels": ["linux"],
    "team_id": "<your-team-uuid>"
  }')

# Start the runner
./run.sh --jitconfig "$(echo "$RESPONSE" | jq -r '.encoded_jit_config')"
```

The runner handles one job then terminates automatically. See [Obtaining credentials](#obtaining-credentials) for how to get a token, and [Teams and label policies](#teams-and-label-policies) for finding your `team_id`.

---

## How it works

```
Your pipeline / workstation
  │
  │  1. Authenticate (OIDC or M2M)
  │
  ▼
GHARTS service
  │  2. Validate credentials & enforce label policies
  │  3. Pre-register runner with GitHub on your behalf
  │
  ▼
GitHub API
  │
  ▼
Runner starts with ./run.sh --jitconfig <config>
```

1. You authenticate to GHARTS with your OIDC token or M2M client credentials.
2. GHARTS validates your identity and checks your team's label policy.
3. GHARTS registers the runner with GitHub, binds labels and ephemeral mode server-side, and hands you a JIT configuration blob.
4. You start the runner binary with `./run.sh --jitconfig <blob>` — no `config.sh` step needed.
5. The runner handles one job then terminates automatically.

---

## Obtaining credentials

### Individual user (OIDC)

Your organization's administrator will tell you:

- The GHARTS service URL (e.g. `https://gharts.example.com`)
- The OIDC issuer URL (e.g. `https://auth.example.com`)
- The OIDC audience value (e.g. `gharts`)

Obtain a Bearer token from your OIDC provider using whichever flow your provider supports (Device Authorization, Authorization Code + PKCE, etc.). The resulting JWT is your credential for every GHARTS API call. See the [OIDC Setup Guide](oidc_setup.md) for detailed configuration instructions and Auth0 setup steps.

```bash
# Example: export your token into an environment variable
export GHARTS_TOKEN="<your-oidc-jwt>"
export GHARTS_URL="https://gharts.example.com"
```

Verify your identity:

```bash
curl -s "$GHARTS_URL/api/v1/auth/me" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .
```

Example response:

```json
{
  "email": "you@example.com",
  "display_name": "Your Name",
  "is_admin": false,
  "can_use_jit": true,
  "can_use_registration_token": false,
  "teams": [
    { "id": "team-uuid", "name": "Backend Team", "role": "member" }
  ]
}
```

Check the label policy that applies to you:

```bash
curl -s "$GHARTS_URL/api/v1/auth/my-label-policy" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .
```

### Automated pipelines (M2M)

For CI/CD pipelines that need to provision runners without a human login, GHARTS supports OAuth 2.0 `client_credentials` (machine-to-machine) flow via Auth0.

**Prerequisites** — your administrator must:

1. Create an Auth0 M2M application for your team.
2. Configure an Auth0 Action to inject a `team` claim into the JWT.
3. Register the client with GHARTS (`POST /api/v1/admin/oauth-clients`).

**Exchanging credentials for a token:**

```bash
# Request an access token from Auth0
TOKEN_RESPONSE=$(curl -s -X POST "https://<your-auth0-domain>/oauth/token" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id":     "<your-client-id>",
    "client_secret": "<your-client-secret>",
    "audience":      "gharts",
    "grant_type":    "client_credentials"
  }')

export GHARTS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')
```

The resulting JWT contains a `team` claim — GHARTS resolves the team automatically on every request, so you never need to pass `team_id` explicitly with M2M tokens.

**Token lifetimes:** Auth0 M2M tokens are short-lived (typically 24 h or less). Re-request a token when yours expires; GHARTS returns `401 Unauthorized` on expiry.

---

## Provisioning runners

### JIT provisioning

With JIT (Just-In-Time) provisioning, the runner is pre-registered with GitHub by GHARTS before you receive the configuration. Labels and ephemeral mode are enforced server-side and cannot be changed by the client.

**Endpoint:** `POST /api/v1/runners/jit`

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `runner_name_prefix` | string | one of name/prefix | Prefix for auto-generated unique name (e.g. `"my-runner"` → `"my-runner-a1b2c3"`) |
| `runner_name` | string | one of name/prefix | Exact runner name |
| `labels` | array of strings | no | Custom labels to request (subject to team policy) |
| `team_id` | UUID string | required if in a team | Team to provision under |

**Example — minimal JIT request:**

```bash
curl -s -X POST "$GHARTS_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $GHARTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "my-runner",
    "labels": ["gpu", "cuda-12"],
    "team_id": "<team-uuid>"
  }' | jq .
```

**Response:**

```json
{
  "runner_id": "abc123...",
  "runner_name": "my-runner-a1b2c3",
  "encoded_jit_config": "eyJhbGciOi...",
  "labels": ["self-hosted", "linux", "x64", "docker", "gpu", "cuda-12"],
  "expires_at": "2026-03-09T15:00:00Z",
  "run_command": "./run.sh --jitconfig eyJhbGciOi..."
}
```

**Starting the runner:**

```bash
JIT_CONFIG=$(echo "$RESPONSE" | jq -r '.encoded_jit_config')

# Native binary
cd actions-runner
./run.sh --jitconfig "$JIT_CONFIG"

# Or with Docker
docker run --rm \
  ghcr.io/actions/actions-runner:latest \
  ./run.sh --jitconfig "$JIT_CONFIG"

# Or with Podman
podman run --rm \
  ghcr.io/actions/actions-runner:latest \
  ./run.sh --jitconfig "$JIT_CONFIG"
```

The JIT config is valid for approximately one hour. The runner is ephemeral — it terminates automatically after executing one workflow job.

**Full shell script example:**

```bash
#!/usr/bin/env bash
set -euo pipefail

GHARTS_URL="https://gharts.example.com"
GHARTS_TOKEN="<your-oidc-token>"
TEAM_ID="<your-team-uuid>"

RESPONSE=$(curl -s -X POST "$GHARTS_URL/api/v1/runners/jit" \
  -H "Authorization: Bearer $GHARTS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"runner_name_prefix\": \"my-runner\",
    \"labels\": [\"linux\", \"docker\"],
    \"team_id\": \"$TEAM_ID\"
  }")

JIT_CONFIG=$(echo "$RESPONSE" | jq -r '.encoded_jit_config')
RUNNER_NAME=$(echo "$RESPONSE" | jq -r '.runner_name')

echo "Starting runner: $RUNNER_NAME"
cd actions-runner
./run.sh --jitconfig "$JIT_CONFIG"
```

**Python example:**

```python
import requests

GHARTS_URL = "https://gharts.example.com"
GHARTS_TOKEN = "<your-oidc-token>"
TEAM_ID = "<your-team-uuid>"

resp = requests.post(
    f"{GHARTS_URL}/api/v1/runners/jit",
    headers={"Authorization": f"Bearer {GHARTS_TOKEN}"},
    json={
        "runner_name_prefix": "my-runner",
        "labels": ["linux", "docker"],
        "team_id": TEAM_ID,
    },
)
resp.raise_for_status()
data = resp.json()

print(f"Runner name : {data['runner_name']}")
print(f"Expires at  : {data['expires_at']}")
print(f"Run command : {data['run_command']}")
```

**Kubernetes Job example:**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: github-runner
spec:
  template:
    spec:
      serviceAccountName: runner-provisioner   # must have OIDC token projection
      containers:
      - name: runner
        image: ghcr.io/actions/actions-runner:latest
        env:
        - name: GHARTS_URL
          value: "https://gharts.example.com"
        - name: TEAM_ID
          value: "<your-team-uuid>"
        command:
        - /bin/bash
        - -c
        - |
          set -e
          OIDC_TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)

          RESPONSE=$(curl -s -X POST "$GHARTS_URL/api/v1/runners/jit" \
            -H "Authorization: Bearer $OIDC_TOKEN" \
            -H "Content-Type: application/json" \
            -d "{
              \"runner_name_prefix\": \"k8s-runner\",
              \"labels\": [\"kubernetes\"],
              \"team_id\": \"$TEAM_ID\"
            }")

          JIT_CONFIG=$(echo "$RESPONSE" | jq -r .encoded_jit_config)
          ./run.sh --jitconfig "$JIT_CONFIG"
      restartPolicy: Never
```

---

## Runner management

### List runners

```bash
# All your runners
curl -s "$GHARTS_URL/api/v1/runners" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .

# Filter by status: active | offline | pending | deleted
curl -s "$GHARTS_URL/api/v1/runners?status=active" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .

# Filter by team
curl -s "$GHARTS_URL/api/v1/runners?team_id=<team-uuid>" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .

# Ephemeral runners only
curl -s "$GHARTS_URL/api/v1/runners?ephemeral=true" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .
```

### Get runner details

```bash
RUNNER_ID="<runner-uuid-from-provision-response>"

curl -s "$GHARTS_URL/api/v1/runners/$RUNNER_ID" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .
```

The response includes the runner's current status, labels, team, and its audit trail (every status change and lifecycle event).

### Refresh runner status

Force a sync with GitHub to update the runner's status:

```bash
curl -s -X POST "$GHARTS_URL/api/v1/runners/$RUNNER_ID/refresh" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .
```

GHARTS also runs a background sync every few minutes automatically.

### Deprovision a runner

Remove a runner from both GHARTS and GitHub:

```bash
curl -s -X DELETE "$GHARTS_URL/api/v1/runners/$RUNNER_ID" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .
```

---

## Teams and label policies

### Viewing your teams

```bash
curl -s "$GHARTS_URL/api/v1/teams/my-teams" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .
```

Each team entry shows:

- `id` — UUID to pass as `team_id` when provisioning
- `name`, `description`
- `required_labels` — labels always applied to your runners
- `optional_label_patterns` — regex patterns; your custom labels must match at least one
- `max_runners` — quota; `null` means unlimited
- `role` — your membership role (`member` or `admin`)

### How label policies work

When you provision a runner under a team, GHARTS applies labels in this order:

1. **System labels** — `self-hosted`, `linux`, `x64` (always present)
2. **Required team labels** — from the team policy (always applied automatically)
3. **Your custom labels** — validated against the team's optional patterns

If a custom label does not match any optional pattern, provisioning is rejected with a `403 Forbidden` and an explanatory message.

**Example:**

```
Team policy:
  required_labels        = ["docker"]
  optional_label_patterns = ["app-.*", "env-.*"]

You request:
  labels = ["app-backend", "gpu"]

Result:
  ✅ "app-backend" matches "app-.*"
  ❌ "gpu" does not match any pattern → 403 Forbidden

Accepted labels would be:
  ["app-backend"]

Final runner labels:
  ["self-hosted", "linux", "x64", "docker", "app-backend"]
```

### Common provisioning errors

| HTTP status | Message | Cause | Action |
|---|---|---|---|
| 401 | Unauthorized | Token missing or expired | Re-authenticate |
| 403 | Label not permitted by team policy | Custom label rejected | Use a label matching your team's patterns |
| 403 | Team quota exceeded | Team at max_runners limit | Remove idle runners or request quota increase |
| 403 | User not a member of team | Wrong team_id | Check `GET /api/v1/teams/my-teams` |
| 403 | Team is inactive | Team deactivated | Contact your administrator |

---

## Using the dashboard

The GHARTS web dashboard is available at `https://gharts.example.com` (your administrator will provide the URL). Sign in with the same OIDC credentials you use for API access.

### Dashboard overview

After sign-in you land on the **Dashboard** home page, which shows:

- **Total runners** — count across all your runners
- **Active** — runners currently idle and ready
- **Offline** — runners registered but unreachable
- **Pending** — runners provisioned but not yet picked up by GitHub
- **Recent activity** — latest provisioning and status-change events

### Runners list

Navigate to **Runners** in the left sidebar to see all your runners in a paginated table. You can:

- Filter by **status** (active / offline / pending / deleted)
- Filter by **team**
- Filter by **ephemeral** flag
- Click a runner name to open its detail page

### Runner detail

The runner detail page shows:

- Current status and labels
- Provisioning method (JIT or registration token)
- Team association
- **Audit trail** — a timestamped log of every lifecycle event for this runner
- **Refresh** button — triggers an on-demand sync with GitHub
- **Deprovision** button — removes the runner

### Provisioning a runner (dashboard)

1. Click **Provision Runner** in the sidebar.
2. If you belong to one or more teams, select a team from the dropdown (required).
3. Enter a **runner name prefix** (optional; a suffix is appended automatically) or an exact name.
4. Enter any **custom labels** as a comma-separated list.
5. Click **Provision JIT Runner**.
6. The response panel shows the runner name, labels, expiry time, and the `run_command` to copy and run on your infrastructure.

### Admin pages

Administrators see additional entries in the sidebar:

| Page | Purpose |
|---|---|
| **Admin → Teams** | Create, edit, deactivate, and reactivate teams |
| **Admin → Teams → Members** | Add or remove users from a team |
| **Admin → Users** | View all users, toggle admin/active flags, edit permissions |
| **Admin → Label Policies** | Manage legacy user-based label policies |
| **Admin → Security Events** | View policy violations, label drift alerts, and unauthorized access attempts (filterable by type, severity, and user) |
| **Admin → Audit Log** | Complete timestamped log of all operations across all users |

---

## Troubleshooting

### `401 Unauthorized`

Your token is missing, malformed, or expired. Re-authenticate with your OIDC provider and retry.

### `403 Forbidden — label not permitted`

The label you requested is not allowed by your team's optional label patterns. Run:

```bash
curl -s "$GHARTS_URL/api/v1/teams/my-teams" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq '.[].optional_label_patterns'
```

Use a label that matches one of the shown patterns, or ask your administrator to update the policy.

### `403 Forbidden — team quota exceeded`

Your team is at its runner limit. List active runners and remove any that are no longer needed:

```bash
curl -s "$GHARTS_URL/api/v1/runners?team_id=<team-uuid>&status=active" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq '.[].runner_id'

# Then deprovision idle ones
curl -s -X DELETE "$GHARTS_URL/api/v1/runners/<runner-id>" \
  -H "Authorization: Bearer $GHARTS_TOKEN"
```

### Runner stays in `pending` state

The runner binary has not connected to GitHub yet. Check that:

1. The JIT config was used before it expired (within ~1 hour of provisioning).
2. The runner binary can reach GitHub's API (`api.github.com`).
3. The runner process started without errors (`./run.sh --jitconfig ...` output).

You can also trigger a manual sync:

```bash
curl -s -X POST "$GHARTS_URL/api/v1/runners/$RUNNER_ID/refresh" \
  -H "Authorization: Bearer $GHARTS_TOKEN" | jq .
```

### Runner shows `offline`

The runner registered with GitHub but is not reachable. This is normal for runners that finished a job but have not yet been removed. GHARTS's periodic sync will transition them to `deleted` automatically. You can also deprovision manually.

### Interactive API docs

GHARTS exposes a full interactive API reference at:

- **Swagger UI:** `https://gharts.example.com/docs`
- **ReDoc:** `https://gharts.example.com/redoc`

Use these to explore all available endpoints, inspect request/response schemas, and try calls directly in your browser.
