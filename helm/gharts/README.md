# GitHub Actions Runner Token Service Helm Chart

This Helm chart deploys the GitHub Actions Runner Token Service (gharts) to Kubernetes.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.13+
- A GitHub App with the required permissions
- An OIDC provider for authentication
- PostgreSQL database (built-in sub-chart for dev; managed database for production)

## Design principle: secrets stay out of Helm values

The chart never creates Secret resources from inline values. All sensitive material
(GitHub private key, OIDC client ID, database credentials) must be pre-loaded into
k8s Secrets before installation. The chart references these Secrets by name.

This means Helm release history is clean of credentials, and secret rotation is
decoupled from chart upgrades.

## Installation

### 1. Create the required k8s Secrets

```bash
# GitHub App private key
kubectl create secret generic gharts-github \
  --from-file=private-key.pem=/path/to/github-app-private-key.pem

# OIDC client ID
kubectl create secret generic gharts-oidc \
  --from-literal=oidc-client-id=<your-oidc-client-id>

# Database connection string (for external database only)
kubectl create secret generic gharts-db \
  --from-literal=DATABASE_URL="postgresql://user:pass@host:5432/gharts?sslmode=require"
```

### 2. Create a values file

```yaml
# my-values.yaml
oidc:
  issuer: "https://auth.example.com/"
  audience: "gharts"
  jwksUrl: "https://auth.example.com/.well-known/jwks.json"
  clientIdSecret: "gharts-oidc"

github:
  organization: "your-org"
  appId: "123456"
  installationId: "12345678"
  privateKeySecret: "gharts-github"

postgresql:
  enabled: false

database:
  databaseUrlSecret: "gharts-db"

ingress:
  hosts:
    - host: gharts.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: gharts-tls
      hosts:
        - gharts.example.com
```

### 3. Install

```bash
# From OCI registry
helm install gharts oci://ghcr.io/afrittoli/gharts --version 1.2.3 -f my-values.yaml

# From local checkout
helm install gharts ./helm/gharts -f my-values.yaml
```

## Configuration reference

### OIDC (`oidc.*`)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `oidc.enabled` | Enable OIDC authentication | `true` |
| `oidc.issuer` | OIDC provider issuer URL (used as authority by frontend) | `""` |
| `oidc.audience` | Expected audience claim | `""` |
| `oidc.jwksUrl` | JWKS URL for backend token validation | `""` |
| `oidc.redirectUri` | Frontend post-login redirect (defaults to ingress host) | `""` |
| `oidc.postLogoutRedirectUri` | Frontend post-logout redirect (defaults to ingress host) | `""` |
| `oidc.clientIdSecret` | **k8s Secret name** containing the OIDC client ID | `""` (required) |
| `oidc.clientIdSecretKey` | Key within the Secret | `"oidc-client-id"` |

### GitHub App (`github.*`)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `github.organization` | GitHub organization name | `""` |
| `github.appId` | GitHub App ID | `""` |
| `github.installationId` | GitHub App installation ID | `""` |
| `github.apiUrl` | GitHub API URL (override for GHES) | `"https://api.github.com"` |
| `github.privateKeySecret` | **k8s Secret name** containing the PEM private key | `""` (required) |
| `github.privateKeySecretKey` | Key within the Secret | `"private-key.pem"` |
| `github.webhookSecret` | **k8s Secret name** for webhook HMAC verification (optional) | `""` |
| `github.webhookSecretKey` | Key within the Secret | `"webhook-secret"` |

### Database

#### Built-in PostgreSQL (`postgresql.*`)

For development and CI only. Uses the [Bitnami PostgreSQL chart](https://github.com/bitnami/charts/tree/main/bitnami/postgresql).
Set `postgresql.enabled: false` for any persistent environment.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Deploy built-in PostgreSQL | `true` |
| `postgresql.auth.username` | Database username | `"gharts"` |
| `postgresql.auth.password` | Database password | `""` |
| `postgresql.auth.database` | Database name | `"gharts"` |

#### External database (`database.*`)

Required when `postgresql.enabled: false`.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `database.sslMode` | SSL mode | `"require"` |
| `database.databaseUrlSecret` | **k8s Secret name** containing full `DATABASE_URL` | `""` (required) |
| `database.databaseUrlSecretKey` | Key within the Secret | `"DATABASE_URL"` |
| `database.poolSize` | Connection pool size | `10` |
| `database.maxOverflow` | Max overflow connections | `20` |
| `database.poolRecycle` | Connection recycle interval (seconds) | `3600` |
| `database.sslCertPath` | Path to SSL client cert (in-container) | `""` |
| `database.sslKeyPath` | Path to SSL client key (in-container) | `""` |
| `database.sslRootCertPath` | Path to SSL root cert (in-container) | `""` |

### Application behavior (`config.*`)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.logLevel` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `"INFO"` |
| `config.accessLogTracing` | Enable detailed access log tracing | `false` |
| `config.adminIdentities` | Comma-separated admin emails or OIDC sub claims | `""` |
| `config.sync.enabled` | Enable background runner sync | `true` |
| `config.sync.intervalSeconds` | Sync interval | `300` |
| `config.sync.onStartup` | Sync on startup | `true` |
| `config.runner.defaultGroupId` | Default runner group ID | `1` |
| `config.runner.tokenExpiryHours` | Registration token expiry (hours) | `1` |
| `config.runner.cleanupStaleHours` | Hours before a runner is considered stale | `24` |
| `config.labelPolicy` | Label policy mode: `audit` or `enforce` | `"audit"` |
| `config.labelDriftDeleteBusyRunners` | Delete runners with label drift even if busy | `false` |

### Pod disruption budgets (`podDisruptionBudget.*`)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `podDisruptionBudget.enabled` | Enable PDBs | `true` |
| `podDisruptionBudget.backend.minAvailable` | Min available backend pods | `1` |
| `podDisruptionBudget.frontend.minAvailable` | Min available frontend pods | `1` |

## Examples

See the [examples](./examples/) directory for environment-specific configurations:

- [Development](./examples/values-development.yaml) — single replica, built-in postgres, port-forward access
- [Staging](./examples/values-staging.yaml) — HA backend, built-in postgres, Let's Encrypt staging
- [Production](./examples/values-production.yaml) — full HA, external managed DB, Prometheus monitoring
- [Kind](./examples/values-kind.yaml) — local kind cluster testing

## Upgrading

```bash
helm upgrade gharts ./helm/gharts -f my-values.yaml
```

## Troubleshooting

### Pods not starting

```bash
kubectl get pods -l app.kubernetes.io/name=gharts
kubectl logs -l app.kubernetes.io/component=backend
kubectl describe pod <pod-name>
```

### Secret not found

If a pod fails with `secret "..." not found`, the referenced k8s Secret does not exist.
Create it with `kubectl create secret` before running `helm install`.

### Database connection issues

```bash
kubectl logs -l app.kubernetes.io/component=backend | grep -i database
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql "$DATABASE_URL"
```
