# Design Documentation

This folder contains detailed design and architecture documentation.

## Contents

- **[token_service.md](token_service.md)** - System architecture, components, data flow, and technical design decisions
- **[dashboard.md](dashboard.md)** - Web dashboard design specifications, requirements, UI/UX, and implementation details
- **[label_policy.md](label_policy.md)** - Label policy enforcement system design and implementation details
- **[github_sync.md](github_sync.md)** - GitHub runner state synchronization mechanism design

## Overview

The Runner Token Service is built with:
- **FastAPI** - Modern async Python web framework
- **SQLAlchemy** - Object-relational mapping for database access
- **SQLite** - Lightweight persistent storage (easily swappable for PostgreSQL)
- **OIDC** - OpenID Connect for third-party authentication
- **GitHub App** - Secure GitHub integration with minimal permissions

## Architecture at a Glance

```
Third Party (OIDC) 
        ↓ (HTTPS + Bearer Token)
Token Service (FastAPI)
        ├── REST API (runners, admin)
        ├── OIDC Validation
        ├── Audit Logging
        └── Database (SQLite/PostgreSQL)
        ↓ (HTTPS + GitHub App Token)
GitHub API
```

See [token_service.md](token_service.md) for complete architecture details.

## Key Design Decisions

1. **OIDC over Direct Credentials** - Allows third parties to use their own identity providers without sharing secrets
2. **GitHub App over PAT** - Provides scoped permissions and better security posture
3. **Time-Limited Tokens** - Registration tokens expire in 1 hour to limit exposure window
4. **User Isolation** - Each user can only manage their own runners
5. **Ephemeral Runners** - Recommended for security; runners execute one job and terminate
6. **Label Policies** - Fine-grained control over runner provisioning
7. **Async Operations** - Non-blocking I/O for better performance

## Dashboard

The web dashboard provides:
- Authenticated access for runners management
- Role-based access (admin vs. standard user)
- Real-time runner status monitoring
- Audit log viewing
- Label policy management

See [dashboard.md](dashboard.md) for detailed specifications.
