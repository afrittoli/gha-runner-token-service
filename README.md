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

## Documentation

### Getting Started
- **[Quick Start Guide](docs/QUICKSTART.md)** - Set up and run in 5 minutes
- **[Usage Examples](docs/USAGE_EXAMPLES.md)** - Practical examples and API usage patterns

### Development
- **[Development Guide](docs/DEVELOPMENT.md)** - Set up development environment, OIDC, Auth0 configuration
- **[Full Documentation](docs/README.md)** - Comprehensive project documentation

### Design & Architecture
- **[Architecture](docs/design/token_service.md)** - System architecture and design decisions
- **[Dashboard Design](docs/design/dashboard.md)** - Web dashboard specifications
- **[Label Policy](docs/design/README.md)** - Label policy enforcement system

## Quick Links

- 📖 [API Documentation](http://localhost:8000/docs) - Interactive Swagger UI (when running)
- 🔧 [CLI Commands](docs/DEVELOPMENT.md#cli-commands) - Administrative commands
- 🐛 [Troubleshooting](docs/QUICKSTART.md#troubleshooting) - Common issues and solutions
- 📋 [Project Summary](docs/README.md) - Project overview and key features

## License

See [LICENSE](LICENSE) file.
