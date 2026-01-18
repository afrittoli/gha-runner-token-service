# GitHub Runner Token Service

A secure central service for managing GitHub self-hosted runner registrations with OIDC authentication.

## Overview

This service acts as a secure intermediary between authenticated third parties and GitHub's runner registration API. It:

- ✅ Authenticates third parties via OIDC
- ✅ Manages GitHub App credentials securely
- ✅ Generates time-limited runner registration tokens
- ✅ Tracks runner lifecycle and state
- ✅ Provides audit trails for runner provisioning
- ✅ Supports automatic cleanup of ephemeral runners

## Architecture

```
Third Party → OIDC Auth → Token Service → GitHub API
                              ↓
                          Database
                       (State Tracking)
```

## Features

### Security
- **OIDC Authentication**: Third parties authenticate with OpenID Connect
- **GitHub App**: Service uses GitHub App with minimal required permissions
- **Time-Limited Tokens**: Registration tokens expire in 1 hour
- **Audit Logging**: All operations tracked with user identity

### Runner Management
- **Provision**: Generate registration tokens for new runners
- **Track**: Monitor runner status (pending, active, offline, deleted)
- **Deprovision**: Remove runners from GitHub
- **Cleanup**: Automatic cleanup of stale/offline runners

### Ephemeral Runners
- Support for single-use ephemeral runners
- Automatic deletion after job completion
- Ideal for secure, isolated CI/CD workloads

## Setup

### 1. Create GitHub App

1. Go to GitHub → Settings → Developer settings → GitHub Apps → New GitHub App
2. Configure:
   - **Name**: Runner Token Service
   - **Webhook**: Uncheck "Active"
   - **Organization permissions**:
     - Self-hosted runners: Read & Write
3. Generate and download private key
4. Install app to your organization
5. Note the App ID and Installation ID

### 2. Install Dependencies

```bash
cd runner-token-service
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

Required configuration:
- `GITHUB_APP_ID`: Your GitHub App ID
- `GITHUB_APP_INSTALLATION_ID`: Installation ID for your org
- `GITHUB_APP_PRIVATE_KEY_PATH`: Path to your GitHub App private key
- `GITHUB_ORG`: Your GitHub organization name
- `OIDC_ISSUER`: Your OIDC provider URL
- `OIDC_AUDIENCE`: Expected audience claim
- `OIDC_JWKS_URL`: OIDC JWKS endpoint

### 4. Initialize Database

```bash
# Create database schema
python -m app.cli init-db
```

### 5. Run Service

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Usage

### Authentication

All requests require OIDC authentication:

```bash
# Get OIDC token from your provider
TOKEN=$(get-oidc-token)

# Use token in API requests
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/runners
```

### Provision a Runner

```bash
curl -X POST http://localhost:8000/api/v1/runners/provision \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name": "ci-worker-001",
    "labels": ["gpu", "ubuntu-22.04", "high-memory"],
    "runner_group_id": 1,
    "ephemeral": true
  }'
```

Response:
```json
{
  "registration_token": "AAABBBCCCDDD...",
  "expires_at": "2026-01-16T15:30:00Z",
  "github_url": "https://github.com/your-org",
  "runner_name": "ci-worker-001",
  "runner_id": "uuid-here",
  "configuration_command": "./config.sh --url https://github.com/your-org --token AAABBB... --name ci-worker-001 --labels gpu,ubuntu-22.04,high-memory --ephemeral"
}
```

### List Your Runners

```bash
curl http://localhost:8000/api/v1/runners \
  -H "Authorization: Bearer $TOKEN"
```

### Get Runner Status

```bash
curl http://localhost:8000/api/v1/runners/ci-worker-001 \
  -H "Authorization: Bearer $TOKEN"
```

### Deprovision a Runner

```bash
curl -X DELETE http://localhost:8000/api/v1/runners/ci-worker-001 \
  -H "Authorization: Bearer $TOKEN"
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Runner Setup (Third Party)

After receiving the registration token, configure the runner:

```bash
# Download runner
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64-2.331.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.331.0/actions-runner-linux-x64-2.331.0.tar.gz
tar xzf ./actions-runner-linux-x64-2.331.0.tar.gz

# Configure with token from API response
./config.sh \
  --url https://github.com/your-org \
  --token AAABBBCCCDDD... \
  --name ci-worker-001 \
  --labels gpu,ubuntu-22.04,high-memory \
  --ephemeral

# Run
./run.sh
```

## Admin Operations

### Cleanup Stale Runners

```bash
# Remove runners offline for more than 1 hour
python -m app.cli cleanup-stale-runners --hours 1
```

### List All Runners (Admin)

```bash
python -m app.cli list-runners
```

### Export Audit Log

```bash
python -m app.cli export-audit-log --since 2026-01-01 --output audit.json
```

## Database Schema

### Tables

- **runners**: Runner registration and state
- **audit_log**: Audit trail of all operations
- **github_runners_cache**: Cached GitHub API data

### Runner States

- `pending`: Registration token issued, runner not yet configured
- `active`: Runner online and accepting jobs
- `offline`: Runner configured but not currently online
- `deleted`: Runner removed from GitHub

## Security Considerations

### Principle of Least Privilege
- GitHub App has minimal permissions (only self-hosted runners)
- Third parties only receive time-limited registration tokens
- Runners are scoped to specific jobs

### Audit Trail
- All operations logged with OIDC identity
- Timestamp and IP address tracking
- Immutable audit log

### Token Security
- Registration tokens expire in 1 hour
- Single-use tokens (recommended to set ephemeral: true)
- Tokens masked in logs

### Recommendations
- Use ephemeral runners for maximum security
- Enable HTTPS in production
- Rotate GitHub App keys regularly
- Monitor audit logs for suspicious activity
- Set up alerts for unusual provisioning patterns

## Development

### Run Tests

```bash
pytest tests/ -v
```

### Code Style

```bash
# Format code
black app/
isort app/

# Lint
flake8 app/
mypy app/
```

### Project Structure

```
runner-token-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── models.py            # Database models
│   ├── schemas.py           # Pydantic schemas (API models)
│   ├── database.py          # Database setup
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── oidc.py          # OIDC authentication
│   │   └── dependencies.py  # Auth dependencies
│   ├── github/
│   │   ├── __init__.py
│   │   ├── client.py        # GitHub API client
│   │   └── app_auth.py      # GitHub App authentication
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── runners.py   # Runner endpoints
│   │       └── admin.py     # Admin endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── runner_service.py    # Runner business logic
│   │   └── cleanup_service.py   # Cleanup operations
│   └── cli.py               # CLI commands
├── tests/
│   ├── __init__.py
│   ├── test_api.py
│   ├── test_github.py
│   └── test_auth.py
├── requirements.txt
├── .env.example
├── README.md
└── alembic/                 # Database migrations
```

## Troubleshooting

### "Invalid GitHub App credentials"
- Verify `GITHUB_APP_ID` and `GITHUB_APP_INSTALLATION_ID`
- Check private key file path and permissions
- Ensure GitHub App is installed to the organization

### "OIDC token validation failed"
- Verify `OIDC_ISSUER` and `OIDC_JWKS_URL`
- Check token audience matches `OIDC_AUDIENCE`
- Ensure token hasn't expired

### "Runner not appearing in GitHub"
- Check registration token hasn't expired (1 hour)
- Verify runner name is unique
- Check runner group permissions
- Review GitHub API rate limits

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: [your-repo]/issues
- Documentation: [your-repo]/wiki
