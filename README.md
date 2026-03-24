# GitHub Runner Token Service (GHARTS)

## What it does

GHARTS is a secure intermediary between your teams and GitHub's runner registration API. Administrators configure the service once with a GitHub App and an OIDC provider; teams then provision runners using their own OIDC credentials (human users via SSO, CI pipelines via scoped M2M client credentials) without ever touching the GitHub App or needing org-level permissions.

Key properties:
- **Credential isolation** — the GitHub App key never leaves the service; each team gets its own narrowly-scoped M2M credential rather than a shared org-level secret
- **Server-side enforcement** — labels, ephemeral mode, and team quotas are bound at provisioning time and cannot be overridden by the client
- **Label drift detection** — the service monitors running jobs and alerts (or removes) runners whose labels were modified after provisioning
- **Full audit trail** — every provisioning event, status change, and policy violation is logged with user identity
- **Admin controls** — user allowlist, team membership, label policies, and M2M client registration are all managed centrally through the API or dashboard

## Documentation

- **[User Guide](docs/user_guide.md)** — how to obtain credentials, provision runners, and use the dashboard
- **[Development Guide](docs/development.md)** — local environment setup, GitHub App config, testing
- **[Kubernetes Deployment](docs/kubernetes_deployment.md)** — deploy to Kubernetes with Helm
- **[Full Documentation](docs/README.md)** — architecture, design docs, and full documentation index

## Development Methodology

This project was developed using **AI-assisted coding** with various AI-based coding assistants.

## License

See [LICENSE](LICENSE) file.
