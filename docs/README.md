# GitHub Runner Token Service - Documentation

## Overview

The **Runner Token Service** is a secure central service that enables third parties to provision GitHub self-hosted runners through OIDC authentication, without exposing privileged credentials.

### What This Solves

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
✅ **Label Policy Enforcement** - Fine-grained control over permitted runner labels
✅ **Time-Limited Tokens** - Registration tokens expire in 1 hour (single-use)
✅ **User Isolation** - Users can only see/manage their own runners
✅ **Ephemeral Support** - Runners auto-delete after one job (recommended)
✅ **Audit Trail** - All operations logged with user identity
✅ **Security Events** - Dedicated logging for policy violations
✅ **Status Tracking** - Sync runner status with GitHub API
✅ **RESTful API** - Clean, documented API with OpenAPI/Swagger
✅ **CLI Tools** - Admin commands for maintenance and monitoring
✅ **Well Structured** - Structured logging, error handling, Docker support

## Documentation Index

### Getting Started
- [Quick Start Guide](QUICKSTART.md) - Get up and running in 5 minutes
- [Usage Examples](USAGE_EXAMPLES.md) - Practical examples and workflows

### Development
- [Development Guide](DEVELOPMENT.md) - Setting up development environment, OIDC configuration

### Design & Architecture
- [Architecture](design/token_service.md) - System design and technical architecture
- [Dashboard Design](design/dashboard.md) - Web dashboard specifications and design
- [Design Overview](design/README.md) - Overview of design documents

## Project Structure

```
runner-token-service/
├── app/                        # Main application
│   ├── api/v1/                # REST API endpoints
│   │   ├── runners.py         # Runner management endpoints
│   │   └── admin.py           # Admin endpoints
│   ├── auth/                   # Authentication
│   │   ├── dependencies.py    # Auth middleware
│   │   └── oidc.py            # OIDC validation
│   ├── services/               # Business logic
│   │   ├── runner_service.py  # Runner provisioning
│   │   └── label_policy_service.py  # Label policy
│   ├── github/                 # GitHub integration
│   │   ├── app_auth.py        # GitHub App auth
│   │   └── client.py          # GitHub API client
│   ├── templates/              # HTML templates
│   │   └── dashboard.html     # Web dashboard
│   ├── models.py              # Database models
│   ├── schemas.py             # API schemas
│   ├── database.py            # Database setup
│   ├── config.py              # Configuration
│   ├── cli.py                 # CLI commands
│   └── main.py                # FastAPI app
├── tests/                      # Test suite
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # Docker compose setup
└── Dockerfile                  # Docker image
```

## Key Concepts

### Runner States

Runners progress through these states:
- **pending**: Runner provisioned but not yet registered with GitHub
- **active**: Runner registered and idle, ready for jobs
- **offline**: Runner registered but offline/unreachable
- **deleted**: Runner removed from GitHub or deprovisioned

### Sync Process

After starting a runner, it remains in "pending" state until synced with GitHub:
```bash
python -m app.cli sync-github
```

This command updates runner statuses to match GitHub's actual state.

### Ephemeral Runners

Ephemeral runners are recommended for security. They:
- Execute a single job
- Automatically terminate
- Clean up their own state
- Ideal for untrusted/third-party code

### Label Policies

Label policies provide fine-grained access control:
- Define which labels users can assign
- Support regex patterns and wildcards
- Validated during provisioning
- Verified post-registration

## Security Considerations

- All API calls require OIDC authentication
- GitHub App uses minimal required permissions
- Registration tokens have 1-hour expiration
- All operations audited and logged
- User isolation prevents cross-user access
- Label policies enforce organizational boundaries

## API Endpoints

See [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) for detailed API examples.

Core endpoints:
- `POST /api/v1/runners/provision` - Generate registration token
- `GET /api/v1/runners` - List user's runners
- `GET /api/v1/runners/{runner_id}` - Get runner details
- `POST /api/v1/runners/{runner_id}/refresh` - Sync status from GitHub
- `DELETE /api/v1/runners/{runner_id}` - Deprovision runner

## CLI Commands

```bash
# Initialize database
python -m app.cli init-db

# Sync with GitHub (update runner statuses)
python -m app.cli sync-github

# List runners
python -m app.cli list-runners

# Cleanup stale runners
python -m app.cli cleanup-stale-runners --hours 24 --dry-run

# Export audit log
python -m app.cli export-audit-log --output audit.json
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for full CLI documentation.

## Support

- 📖 [Full API Documentation](http://localhost:8000/docs) - Interactive Swagger UI
- 🔗 [GitHub Repository](https://github.com/afrittoli/gha-runner-token-service)
- 📝 [Issues & Discussions](https://github.com/afrittoli/gha-runner-token-service/issues)
