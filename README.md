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
- ✅ **Team-based authorization** with label policies and quotas
- ✅ **JIT (Just-In-Time) provisioning** with server-side label enforcement

> [!WARNING]
> This repo contains an MVP developed as proof-of-concept. It is not ready for production use.

## Quick Start

### Kubernetes Deployment (Recommended)

Install using Helm from OCI registry:

```bash
helm install gharts oci://ghcr.io/afrittoli/gharts --version latest \
  --set config.githubAppId=YOUR_APP_ID \
  --set config.githubAppPrivateKey="YOUR_PRIVATE_KEY" \
  --set config.oidcClientId=YOUR_CLIENT_ID \
  --set config.oidcClientSecret=YOUR_CLIENT_SECRET \
  --set config.oidcDiscoveryUrl=YOUR_OIDC_URL \
  --set bootstrap.admin.password=SECURE_PASSWORD
```

See [Kubernetes Deployment Guide](docs/kubernetes_deployment.md) for detailed instructions.

### Local Development

```bash
# Clone and setup
git clone https://github.com/afrittoli/gha-runner-token-service.git
cd gha-runner-token-service

# Run with Kind
make kind-setup
make build && make kind-deploy
```

See [Development Guide](docs/development.md) for more details.

## Documentation

### Getting Started
- **[Quick Start Guide](docs/quickstart.md)** - Set up and run in 5 minutes
- **[Kubernetes Deployment](docs/kubernetes_deployment.md)** - Deploy to Kubernetes with Helm
- **[Usage Examples](docs/usage_examples.md)** - Practical examples and API usage patterns

### Deployment
- **[Deployment Checklist](docs/deployment_checklist.md)** - Production deployment guide
- **[Helm Chart](helm/gharts/README.md)** - Helm chart documentation
- **[Helm Release Process](docs/helm_chart_release.md)** - Chart release and versioning

### Development
- **[Development Guide](docs/development.md)** - Set up development environment, OIDC, Auth0 configuration
- **[Full Documentation](docs/README.md)** - Comprehensive project documentation

### Design & Architecture
- **[Architecture](docs/design/token_service.md)** - System architecture and design decisions
- **[Dashboard Design](docs/design/dashboard.md)** - Web dashboard specifications
- **[Label Policy](docs/design/README.md)** - Label policy enforcement system
- **[Team Management](docs/team_management.md)** - Team-based authorization guide

## Quick Links

- 📖 [API Documentation](http://localhost:8000/docs) - Interactive Swagger UI (when running)
- 🔧 [CLI Commands](docs/DEVELOPMENT.md#cli-commands) - Administrative commands
- 🐛 [Troubleshooting](docs/QUICKSTART.md#troubleshooting) - Common issues and solutions
- 📋 [Project Summary](docs/README.md) - Project overview and key features

## Development Methodology

This project was developed using **AI-assisted coding** (also known as "vibe coding") with various AI-based coding assistants.

The AI assistants helped with:
- Documentation of the design and structure in TODOs
- Implementation of the backend and frontend
- Code generation and refactoring
- Test creation and debugging
- Documentation writing
- Best practices and security considerations

## License

See [LICENSE](LICENSE) file.
