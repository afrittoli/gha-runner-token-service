# Quick Start Guide

Get the Runner Token Service up and running in 5 minutes.

## Prerequisites

- Python 3.11+
- A GitHub organization
- GitHub App with "Self-hosted runners: Read & Write" permission

## Step 1: Create GitHub App (5 minutes)

1. Go to GitHub → Settings → Developer settings → GitHub Apps → [New GitHub App](https://github.com/settings/apps/new)

2. Configure:
   ```
   Name: Runner Token Service (or any name)
   Homepage URL: http://localhost:8000
   Webhook: ☐ Active (uncheck this)

   Organization permissions:
   - Self-hosted runners: Read and write
   ```

3. Click "Create GitHub App"

4. **Generate Private Key**:
   - Scroll down → "Private keys" → "Generate a private key"
   - Save the downloaded `.pem` file

5. **Install to Organization**:
   - Click "Install App" in left sidebar
   - Select your organization
   - Click "Install"

6. **Get IDs**:
   - App ID: shown on app settings page
   - Installation ID: in URL after installing (`.../installations/{INSTALLATION_ID}`)

## Step 2: Setup Service (2 minutes)

```bash
# Clone/navigate to service directory
cd runner-token-service

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy GitHub App private key
cp ~/Downloads/your-app.*.private-key.pem ./github-app-private-key.pem
chmod 600 github-app-private-key.pem

# Create configuration
cat > .env <<EOF
# GitHub Configuration
GITHUB_APP_ID=YOUR_APP_ID_HERE
GITHUB_APP_INSTALLATION_ID=YOUR_INSTALLATION_ID_HERE
GITHUB_APP_PRIVATE_KEY_PATH=./github-app-private-key.pem
GITHUB_ORG=your-org-name

# OIDC (disabled for testing)
ENABLE_OIDC_AUTH=false
OIDC_ISSUER=https://example.com
OIDC_AUDIENCE=runner-token-service
OIDC_JWKS_URL=https://example.com/.well-known/jwks.json

# Database
DATABASE_URL=sqlite:///./runner_service.db

# Service
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8000
LOG_LEVEL=INFO
EOF

# Initialize database
python -m app.cli init-db
```

## Step 3: Start Service (1 minute)

```bash
# Start the service
uvicorn app.main:app --reload

# Service is now running at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Step 4: Test It (2 minutes)

### Provision a Runner

You can provision a runner using either a name prefix or an exact name:

**Option 1: Using a name prefix (recommended)**

The service generates a unique name by appending a random suffix to your prefix:

```bash
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/runners/provision \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "test-runner",
    "labels": ["test", "linux"],
    "ephemeral": true
  }')
echo "$RESPONSE" | jq .
```

**Option 2: Using an exact name**

```bash
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/runners/provision \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name": "my-specific-runner",
    "labels": ["test", "linux"],
    "ephemeral": true
  }')
echo "$RESPONSE" | jq .
```

Example response:
```json
{
  "runner_id": "abc123...",
  "runner_name": "test-runner-a1b2c3",
  "registration_token": "AABBCCDD...",
  "expires_at": "2026-01-16T15:30:00Z",
  "github_url": "https://github.com/your-org",
  "runner_group_id": 1,
  "ephemeral": true,
  "labels": ["test", "linux"],
  "configuration_command": "./config.sh --url https://github.com/your-org --token AABBCCDD... --name test-runner-a1b2c3 --unattended --labels test,linux --ephemeral"
}
```

**Note:** When using exact names, you cannot reuse a name that's currently active.
Once a runner is deleted (or an ephemeral runner completes), the name can be reused.

Extract the values needed for the following steps:

```bash
CONFIG_CMD=$(echo "$RESPONSE" | jq -r '.configuration_command')
RUNNER_ID=$(echo "$RESPONSE" | jq -r '.runner_id')
RUNNER_NAME=$(echo "$RESPONSE" | jq -r '.runner_name')
```

### Start the Runner

#### Option A: Podman Container (macOS/Linux)

This is the recommended approach for local testing on macOS since the GitHub runner binary is Linux-only.

```bash
podman run -it --rm \
  ghcr.io/actions/actions-runner:latest \
  bash -c "$CONFIG_CMD && ./run.sh"
```

**Notes for macOS with Podman:**
- The container runs a Linux VM under the hood via `podman machine`
- To access the token service from inside the container, use `host.containers.internal:8000` instead of `localhost:8000`
- Make sure `podman machine` is running: `podman machine start`

#### Option B: Directly on Linux

```bash
# 1. Download runner
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.331.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.331.0/actions-runner-linux-x64-2.331.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.331.0.tar.gz

# 2. Configure and start
$CONFIG_CMD
./run.sh
```

### Sync Runner Status with GitHub

**Important:** After starting the runner, it will appear in a "pending" state in the service until you sync with GitHub. Run the sync command to update the runner status to "active" or "offline".

```bash
# Sync all runners with GitHub API
# This checks which runners have been registered and updates their status
python -m app.cli sync-github
```

After syncing, the runner status should change from "pending" to "active".

### Check Runner Status

```bash
# List all runners
curl http://localhost:8000/api/v1/runners | jq .

# Get specific runner by ID
curl http://localhost:8000/api/v1/runners/$RUNNER_ID | jq .

# Refresh status from GitHub
curl -X POST http://localhost:8000/api/v1/runners/$RUNNER_ID/refresh | jq .
```

### Delete Runner

```bash
curl -X DELETE http://localhost:8000/api/v1/runners/$RUNNER_ID | jq .
```

## Verify in GitHub

1. Go to your GitHub organization
2. Settings → Actions → Runners
3. You should see your runner (`$RUNNER_NAME`) in the list

## Next Steps

### Enable OIDC Authentication

For production use, enable OIDC:

```bash
# Edit .env
ENABLE_OIDC_AUTH=true
OIDC_ISSUER=https://your-oidc-provider.com
OIDC_AUDIENCE=runner-token-service
OIDC_JWKS_URL=https://your-oidc-provider.com/.well-known/jwks.json

# Restart service
```

Then include OIDC token in requests:
```bash
curl -X POST http://localhost:8000/api/v1/runners/provision \
  -H "Authorization: Bearer YOUR_OIDC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '...'
```

### Explore API

Visit http://localhost:8000/docs for interactive API documentation (Swagger UI).

### CLI Commands

```bash
# List all runners
python -m app.cli list-runners

# Sync with GitHub
python -m app.cli sync-github

# Cleanup stale runners
python -m app.cli cleanup-stale-runners --hours 24 --dry-run

# Export audit log
python -m app.cli export-audit-log --output audit.json
```

### Deploy to Production

See [README.md](README.md) for:
- Docker deployment
- Kubernetes setup
- Production configuration
- Security best practices

## Troubleshooting

### "Failed to generate GitHub token"

- Verify `GITHUB_APP_ID` is correct
- Verify `GITHUB_APP_INSTALLATION_ID` is correct
- Check private key file exists and is readable
- Ensure GitHub App is installed to the organization
- Check GitHub App has "Self-hosted runners: Read & Write" permission

### "Runner not appearing in GitHub"

- Wait 30 seconds after provisioning
- Check token hasn't expired (1 hour limit)
- Verify runner name is unique
- Check runner was configured with correct token

### API returns 404

- Ensure you're using the correct endpoint: `/api/v1/runners/provision`
- Service should be running on port 8000
- Check logs: `uvicorn app.main:app --log-level debug`

## Support

- Full documentation: [README.md](README.md)
- Usage examples: [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md)
- API docs: http://localhost:8000/docs (when running)
