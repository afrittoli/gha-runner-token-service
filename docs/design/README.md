# Design Documentation

This folder contains detailed design and architecture documentation.

## Diagrams

| Diagram | Description |
|---------|-------------|
| [Data Model](../diagrams/data_model.svg) | Database schema for all core tables |
| [JIT Flow](../diagrams/jit_flow.svg) | End-to-end JIT runner provisioning flow |
| [OIDC Architecture](../diagrams/oidc_architecture.svg) | Authentication architecture with OIDC and M2M token paths |

## Design Documents

| Document | Description |
|----------|-------------|
| [backend.md](backend.md) | Backend architecture: system overview, authentication, data model, label policy enforcement, and observability |
| [team_based_authorization.md](team_based_authorization.md) | Team-based authorization design and implementation |
| [dashboard.md](dashboard.md) | Web dashboard design specifications, requirements, UI/UX, and implementation details |
| [kubernetes_deployment.md](kubernetes_deployment.md) | Kubernetes deployment architecture |
| [arc.md](arc.md) | Actions Runner Controller (ARC) integration design |

## Overview

The Runner Token Service is built with:
- **FastAPI** - Modern async Python web framework
- **SQLAlchemy** - Object-relational mapping for database access
- **PostgreSQL** - Persistent storage
- **OIDC** - OpenID Connect for third-party authentication
- **GitHub App** - Secure GitHub integration with minimal permissions
