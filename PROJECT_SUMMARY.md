# GitHub Runner Token Service - Project Summary

## Overview

This is a **prototype** of a secure central service that enables third parties to provision GitHub self-hosted runners through OIDC authentication, without exposing privileged credentials.

## What This Solves

**Problem**: You want third parties to provision GitHub self-hosted runners, but don't want to give them:
- Your GitHub PAT (too much access)
- Direct access to GitHub App credentials (security risk)
- Ability to provision runners for other users (isolation concern)

**Solution**: This service acts as a secure intermediary:
1. Third party authenticates with OIDC (their identity provider)
2. Service validates OIDC token and generates GitHub registration token
3. Third party uses token to configure runner (expires in 1 hour)
4. Service tracks all runners and maintains audit trail

## Key Features

✅ **OIDC Authentication** - Third parties authenticate with their own identity provider
✅ **GitHub App Integration** - Service uses GitHub App with minimal required permissions
✅ **Label Policy Enforcement** - Fine-grained control over permitted runner labels with validation and verification
✅ **Time-Limited Tokens** - Registration tokens expire in 1 hour (single-use)
✅ **User Isolation** - Users can only see/manage their own runners
✅ **Ephemeral Support** - Runners auto-delete after one job (recommended)
✅ **Audit Trail** - All operations logged with user identity
✅ **Security Events** - Dedicated logging for policy violations and security incidents
✅ **Status Tracking** - Sync runner status with GitHub API
✅ **RESTful API** - Clean, documented API with OpenAPI/Swagger
✅ **CLI Tools** - Admin commands for maintenance and monitoring
✅ **Well Structured** - Structured logging, error handling, Docker support

## Project Structure

```
runner-token-service/
├── app/
│   ├── api/v1/           # REST API endpoints
│   │   └── runners.py    # Runner provisioning/management
│   ├── auth/             # Authentication
│   │   ├── oidc.py       # OIDC token validation
│   │   └── dependencies.py
│   ├── github/           # GitHub API integration
│   │   ├── app_auth.py   # GitHub App JWT auth
│   │   └── client.py     # GitHub API client
│   ├── services/         # Business logic
│   │   └── runner_service.py
│   ├── config.py         # Configuration management
│   ├── database.py       # Database setup
│   ├── models.py         # SQLAlchemy models
│   ├── schemas.py        # Pydantic API schemas
│   ├── main.py           # FastAPI application
│   └── cli.py            # CLI commands
├── tests/                # Unit tests
├── README.md             # Full documentation
├── QUICKSTART.md         # 5-minute setup guide
├── USAGE_EXAMPLES.md     # API usage examples
├── ARCHITECTURE.md       # Technical architecture
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker image
└── docker-compose.yml    # Docker Compose config
```

## Technology Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: SQLAlchemy (SQLite default, PostgreSQL recommended for production)
- **Authentication**: OIDC with JWKS validation (python-jose)
- **GitHub API**: PyJWT for GitHub App authentication, httpx for HTTP
- **Logging**: Structlog (JSON structured logs)
- **Testing**: pytest
- **Deployment**: Docker, Docker Compose, or direct deployment

## API Endpoints

### Runner Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/health` | Health check | No |
| POST | `/api/v1/runners/provision` | Provision new runner | OIDC |
| GET | `/api/v1/runners` | List user's runners | OIDC |
| GET | `/api/v1/runners/{name}` | Get runner status | OIDC |
| POST | `/api/v1/runners/{name}/refresh` | Sync with GitHub | OIDC |
| DELETE | `/api/v1/runners/{name}` | Delete runner | OIDC |

### Label Policy Administration

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/v1/admin/label-policies` | Create/update label policy | Admin |
| GET | `/api/v1/admin/label-policies` | List all label policies | Admin |
| GET | `/api/v1/admin/label-policies/{user}` | Get policy for user | Admin |
| DELETE | `/api/v1/admin/label-policies/{user}` | Delete label policy | Admin |
| GET | `/api/v1/admin/security-events` | Query security events | Admin |

## CLI Commands

```bash
python -m app.cli init-db                    # Initialize database
python -m app.cli list-runners               # List all runners
python -m app.cli cleanup-stale-runners      # Cleanup offline runners
python -m app.cli sync-github                # Sync status with GitHub
python -m app.cli export-audit-log           # Export audit trail
```

## Quick Start (5 Minutes)

```bash
# 1. Setup
cd runner-token-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure (edit with your values)
cp .env.example .env
# Add: GITHUB_APP_ID, GITHUB_APP_INSTALLATION_ID, GITHUB_ORG
# Place GitHub App private key as: github-app-private-key.pem

# 3. Initialize
python -m app.cli init-db

# 4. Run
uvicorn app.main:app --reload

# 5. Test (OIDC disabled for testing)
curl -X POST http://localhost:8000/api/v1/runners/provision \
  -H "Content-Type: application/json" \
  -d '{"runner_name": "test-runner", "labels": ["test"], "ephemeral": true}'
```

Full instructions in [QUICKSTART.md](QUICKSTART.md).

## Security Model

### Authorization Hierarchy

```
GitHub App (Org Admin)
  ↓ Installation Token (1h)
    ↓ Registration Token (1h, single-use)
      ↓ Runner OAuth Token (runner lifetime)
        ↓ Job Token (job duration)
```

### Access Control

- **Service**: Holds GitHub App credentials (never exposed)
- **Third Party**: Gets time-limited registration token via OIDC
- **Runner**: Self-generates OAuth credentials using RSA keypair
- **Jobs**: Receive job-scoped tokens from GitHub

### Audit Trail

Every operation logged:
- User identity (from OIDC)
- Timestamp
- Action (provision, deprovision, etc.)
- Result (success/failure)
- Event data

## Data Model

### Runner

```python
{
  "id": "uuid",
  "runner_name": "unique-name",
  "github_runner_id": 12345,  # Set after registration
  "status": "pending|active|offline|deleted",
  "labels": ["gpu", "linux"],
  "ephemeral": true,
  "provisioned_by": "user@example.com",
  "created_at": "2026-01-16T12:00:00Z",
  "registered_at": "2026-01-16T12:05:00Z"
}
```

### Audit Log

```python
{
  "event_type": "provision",
  "runner_name": "gpu-worker",
  "user_identity": "user@example.com",
  "success": true,
  "timestamp": "2026-01-16T12:00:00Z"
}
```

## Example Usage

### Provision Runner

```bash
curl -X POST http://localhost:8000/api/v1/runners/provision \
  -H "Authorization: Bearer ${OIDC_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name": "gpu-worker-001",
    "labels": ["gpu", "ubuntu-22.04"],
    "ephemeral": true
  }'
```

### Configure Runner

```bash
# On target machine
./config.sh \
  --url https://github.com/my-org \
  --token ${REGISTRATION_TOKEN} \
  --name gpu-worker-001 \
  --labels gpu,ubuntu-22.04 \
  --ephemeral

./run.sh
```

## Deployment Options

### Local Development

```bash
uvicorn app.main:app --reload
```

### Docker

```bash
docker build -t runner-token-service .
docker run -p 8000:8000 runner-token-service
```

### Docker Compose

```bash
docker-compose up
```

### Kubernetes

See [ARCHITECTURE.md](ARCHITECTURE.md) for Kubernetes deployment example.

## Testing

### Without OIDC (Development)

```bash
# In .env
ENABLE_OIDC_AUTH=false

# Requests don't need Authorization header
curl -X POST http://localhost:8000/api/v1/runners/provision ...
```

### With OIDC (Production)

```bash
# Get token from your OIDC provider
OIDC_TOKEN=$(get-oidc-token)

# Include in requests
curl -H "Authorization: Bearer $OIDC_TOKEN" ...
```

### Unit Tests

```bash
pytest tests/ -v
```

## Configuration

### Required Settings

```bash
GITHUB_APP_ID=123456
GITHUB_APP_INSTALLATION_ID=12345678
GITHUB_APP_PRIVATE_KEY_PATH=./github-app-private-key.pem
GITHUB_ORG=my-org
```

### OIDC Settings

```bash
OIDC_ISSUER=https://auth.example.com
OIDC_AUDIENCE=runner-token-service
OIDC_JWKS_URL=https://auth.example.com/.well-known/jwks.json
ENABLE_OIDC_AUTH=true
```

### Optional Settings

```bash
DATABASE_URL=sqlite:///./runner_service.db  # Or PostgreSQL
SERVICE_PORT=8000
LOG_LEVEL=INFO
```

## Documentation Files

| File | Description |
|------|-------------|
| [README.md](README.md) | Complete documentation and setup guide |
| [QUICKSTART.md](QUICKSTART.md) | 5-minute quick start guide |
| [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) | API usage examples and integration patterns |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture and design decisions |
| [LABEL_POLICY.md](LABEL_POLICY.md) | Label policy enforcement system documentation |
| `.env.example` | Environment configuration template |

## Production Considerations

### Scaling

- Use PostgreSQL instead of SQLite
- Deploy multiple API instances behind load balancer
- Add Redis for shared cache (installation tokens)

### Security

- Enable OIDC authentication (`ENABLE_OIDC_AUTH=true`)
- Configure label policies for all users to enforce authorization boundaries
- Use HTTPS (TLS termination at load balancer)
- Rotate GitHub App keys regularly
- Monitor audit logs and security events for suspicious activity
- Set up alerts for policy violations and failed authentication attempts
- Enable restrictive default policy behavior in production environments

### Monitoring

- Structured JSON logs for log aggregation
- Health check endpoint for load balancer probes
- Export metrics to Prometheus (future enhancement)
- Set up alerts for:
  - High error rate
  - GitHub API rate limits
  - Database connection issues

### Backup

- Database: Regular backups (critical: runner state and audit log)
- GitHub App private key: Secure backup storage

## Limitations & Future Enhancements

### Current Limitations

- Single organization support (can be extended to multi-org)
- No per-user quotas (can be added)
- Manual status refresh (could use GitHub webhooks)
- SQLite default (PostgreSQL recommended for production)

### Planned Enhancements

1. **Webhooks**: Real-time runner status updates from GitHub
2. **Quotas**: Per-user runner limits
3. **Runner Groups**: Advanced group management
4. **Auto-scaling**: Dynamic provisioning based on job queue
5. **Web Dashboard**: UI for runner management
6. **Metrics**: Prometheus endpoint
7. **Multi-org**: Support multiple GitHub organizations

## License

MIT License - See [LICENSE](LICENSE) file

## Support & Contributing

This is a prototype implementation. For production use:
1. Review security settings
2. Test thoroughly in staging environment
3. Configure monitoring and alerting
4. Set up backup procedures
5. Document your OIDC integration

## Summary

This service provides a **secure, auditable, and scalable solution** for allowing third parties to provision GitHub self-hosted runners without exposing privileged credentials. The implementation is well-documented and follows security best practices.

**Key Benefits:**
- ✅ Security: Least privilege principle, OIDC authentication
- ✅ Isolation: Users can only manage their own runners
- ✅ Audit: Complete audit trail of all operations
- ✅ Simplicity: Clean API, easy integration
- ✅ Flexibility: Supports ephemeral and persistent runners

**Get Started:** See [QUICKSTART.md](QUICKSTART.md) for a 5-minute setup guide.
