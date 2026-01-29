# Quick Start Guide

Get the Runner Token Service up and running in 5 minutes.

## Prerequisites

- Python 3.11+
- A GitHub organization
- GitHub App with "Self-hosted runners: Read & Write" permission
- Podman or Docker (for running runners on macOS)

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

## Step 4: Provision a Runner with JIT (Recommended)

JIT (Just-In-Time) provisioning is the recommended approach because it enforces labels and ephemeral mode server-side, preventing clients from bypassing security policies.

### Provision using JIT API

```bash
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/runners/jit \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "test-runner",
    "labels": ["test", "linux"],
    "runner_group_id": 1
  }')
echo "$RESPONSE" | jq .
```

Example response:
```json
{
  "runner_id": "abc123...",
  "runner_name": "test-runner-a1b2c3",
  "encoded_jit_config": "eyJydW5uZXIiOi...(base64 encoded)...",
  "labels": ["self-hosted", "Linux", "X64", "test", "linux"],
  "expires_at": "2026-01-21T15:30:00Z",
  "run_command": "./run.sh --jitconfig <encoded_jit_config>"
}
```

Extract values for the next steps:

```bash
JIT_CONFIG=$(echo "$RESPONSE" | jq -r '.encoded_jit_config')
RUNNER_ID=$(echo "$RESPONSE" | jq -r '.runner_id')
RUNNER_NAME=$(echo "$RESPONSE" | jq -r '.runner_name')
```

### Start the Runner

#### Option A: Podman Container (macOS/Linux) - Recommended

```bash
podman run -it --rm \
  ghcr.io/actions/actions-runner:latest \
  ./run.sh --jitconfig "$JIT_CONFIG"
```

**Notes for macOS with Podman:**
- The container runs a Linux VM under the hood via `podman machine`
- Make sure `podman machine` is running: `podman machine start`

#### Option B: Directly on Linux

```bash
# 1. Download runner
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.321.0.tar.gz

# 2. Start directly with JIT config (no config.sh needed!)
./run.sh --jitconfig "$JIT_CONFIG"
```

### JIT Benefits

| Feature | Registration Token | JIT |
|---------|-------------------|-----|
| Label enforcement | Client-side (can be bypassed) | **Server-side (enforced)** |
| Ephemeral mode | Optional | **Always enabled** |
| Configuration step | Required (`config.sh`) | **Not needed** |
| Security | Token can be misused | **Config is single-use, pre-bound** |

### Check Runner Status

```bash
# List all runners
curl http://localhost:8000/api/v1/runners | jq .

# Get specific runner by ID
curl http://localhost:8000/api/v1/runners/$RUNNER_ID | jq .
```

**Note:** JIT runners are immediately registered with GitHub. The periodic sync service (runs every 5 minutes) will update runner status automatically. No manual sync is required.

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
curl -X POST http://localhost:8000/api/v1/runners/jit \
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

# Sync with GitHub (usually automatic via periodic sync)
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

## Alternative: Registration Token API

For cases where you need more control over the runner configuration, the registration token API is available. See [development.md](development.md#alternative-registration-token-api) for details.

**Note:** The registration token API allows clients to potentially bypass label and ephemeral settings. Use JIT for production environments.

## Troubleshooting

### "Failed to generate GitHub token"

- Verify `GITHUB_APP_ID` is correct
- Verify `GITHUB_APP_INSTALLATION_ID` is correct
- Check private key file exists and is readable
- Ensure GitHub App is installed to the organization
- Check GitHub App has "Self-hosted runners: Read & Write" permission

### "Runner not appearing in GitHub"

- JIT runners should appear immediately after provisioning
- Verify the JIT config hasn't expired (~1 hour validity)
- Check the runner started successfully: `podman logs <container>`

### API returns 404

- For JIT: use `/api/v1/runners/jit`
- For registration tokens: use `/api/v1/runners/provision`
- Service should be running on port 8000
- Check logs: `uvicorn app.main:app --log-level debug`

### Runner shows "offline" status

- The runner process may have exited
- For ephemeral runners: this is expected after completing one job
- Check runner logs for errors

## Support

- Full documentation: [README.md](README.md)
- JIT design: [JIT Provisioning Design](design/jit_provisioning.md)
- Usage examples: [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md)
- API docs: http://localhost:8000/docs (when running)
