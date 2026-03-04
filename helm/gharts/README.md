# GitHub Actions Runner Token Service Helm Chart

This Helm chart deploys the GitHub Actions Runner Token Service to Kubernetes.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.13+
- PostgreSQL database (can be deployed with this chart)
- GitHub App credentials
- OIDC provider configuration

## Installation

### From OCI Registry (Recommended)

The chart is published to GitHub Container Registry (GHCR) and can be installed directly:

```bash
# Install latest stable release
helm install gharts oci://ghcr.io/afrittoli/gharts --version latest

# Install specific version
helm install gharts oci://ghcr.io/afrittoli/gharts --version 1.2.3

# Install with custom values
helm install gharts oci://ghcr.io/afrittoli/gharts \
  --version 1.2.3 \
  -f my-values.yaml
```

### From Local Chart

```bash
# Clone the repository
git clone https://github.com/afrittoli/gha-runner-token-service.git
cd gha-runner-token-service

# Install the chart
helm install gharts ./helm/gharts -f my-values.yaml
```

### From GitHub Release

```bash
# Download chart from release
wget https://github.com/afrittoli/gha-runner-token-service/releases/download/v1.2.3/gharts-1.2.3.tgz

# Install from downloaded file
helm install gharts ./gharts-1.2.3.tgz -f my-values.yaml
```

## Quick Start

Create a values file with your configuration:

```bash
cat > my-values.yaml <<EOF
config:
  githubAppId: "YOUR_APP_ID"
  githubAppPrivateKey: |
    -----BEGIN RSA PRIVATE KEY-----
    YOUR_PRIVATE_KEY
    -----END RSA PRIVATE KEY-----
  oidcClientId: "YOUR_CLIENT_ID"
  oidcClientSecret: "YOUR_CLIENT_SECRET"
  oidcDiscoveryUrl: "https://your-oidc-provider/.well-known/openid-configuration"

bootstrap:
  admin:
    password: "SECURE_PASSWORD"
EOF

# Install from OCI registry
helm install gharts oci://ghcr.io/afrittoli/gharts --version latest -f my-values.yaml
```

## Common Installation Scenarios

### Using External PostgreSQL

```bash
helm install gharts oci://ghcr.io/afrittoli/gharts \
  --version latest \
  --set postgresql.enabled=false \
  --set config.databaseUrl="postgresql://user:pass@host:5432/dbname" \
  -f my-values.yaml
```

### With Ingress

```bash
helm install gharts oci://ghcr.io/afrittoli/gharts \
  --version latest \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=gharts.example.com \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix \
  -f my-values.yaml
```

## Version Management

The chart is published with multiple tags for flexibility:

| Tag | Description | Example |
|-----|-------------|---------|
| `latest` | Latest stable release | `helm install gharts oci://ghcr.io/afrittoli/gharts --version latest` |
| `1.2.3` | Specific version | `helm install gharts oci://ghcr.io/afrittoli/gharts --version 1.2.3` |
| `1.2` | Latest patch in 1.2.x | `helm install gharts oci://ghcr.io/afrittoli/gharts --version 1.2` |
| `1` | Latest minor in 1.x | `helm install gharts oci://ghcr.io/afrittoli/gharts --version 1` |
| `main` | Latest from main branch (testing) | `helm install gharts oci://ghcr.io/afrittoli/gharts --version main` |
| `sha-<commit>` | Specific commit (testing) | `helm install gharts oci://ghcr.io/afrittoli/gharts --version sha-abc123` |

**Recommendation**: Use specific versions (e.g., `1.2.3`) in production for reproducibility.

## Configuration

### Image Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.backend.repository` | Backend image repository | `ghcr.io/your-org/gha-runner-token-service-backend` |
| `image.backend.tag` | Backend image tag | `latest` |
| `image.backend.pullPolicy` | Backend image pull policy | `IfNotPresent` |
| `image.frontend.repository` | Frontend image repository | `ghcr.io/your-org/gha-runner-token-service-frontend` |
| `image.frontend.tag` | Frontend image tag | `latest` |
| `image.frontend.pullPolicy` | Frontend image pull policy | `IfNotPresent` |

### Application Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `config.githubAppId` | GitHub App ID | `""` |
| `config.githubAppPrivateKey` | GitHub App private key | `""` |
| `config.oidcClientId` | OIDC client ID | `""` |
| `config.oidcClientSecret` | OIDC client secret | `""` |
| `config.oidcDiscoveryUrl` | OIDC discovery URL | `""` |
| `config.logLevel` | Log level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `config.corsOrigins` | CORS allowed origins | `*` |

### Database Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Deploy PostgreSQL with the chart | `true` |
| `postgresql.auth.username` | PostgreSQL username | `gharts` |
| `postgresql.auth.password` | PostgreSQL password | `changeme` |
| `postgresql.auth.database` | PostgreSQL database name | `gharts` |
| `config.databaseUrl` | External database URL (if postgresql.enabled=false) | `""` |
| `config.databasePoolSize` | Database connection pool size | `20` |
| `config.databaseMaxOverflow` | Database connection pool max overflow | `10` |

### Bootstrap Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `bootstrap.enabled` | Enable bootstrap admin creation | `true` |
| `bootstrap.admin.username` | Bootstrap admin username | `admin` |
| `bootstrap.admin.password` | Bootstrap admin password | `changeme` |
| `bootstrap.admin.email` | Bootstrap admin email | `admin@example.com` |

### Backend Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount.backend` | Number of backend replicas | `2` |
| `backend.resources.limits.cpu` | Backend CPU limit | `1000m` |
| `backend.resources.limits.memory` | Backend memory limit | `1Gi` |
| `backend.resources.requests.cpu` | Backend CPU request | `500m` |
| `backend.resources.requests.memory` | Backend memory request | `512Mi` |
| `backend.autoscaling.enabled` | Enable backend autoscaling | `false` |
| `backend.autoscaling.minReplicas` | Minimum backend replicas | `2` |
| `backend.autoscaling.maxReplicas` | Maximum backend replicas | `10` |
| `backend.autoscaling.targetCPUUtilizationPercentage` | Target CPU for autoscaling | `70` |

### Frontend Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount.frontend` | Number of frontend replicas | `2` |
| `frontend.resources.limits.cpu` | Frontend CPU limit | `500m` |
| `frontend.resources.limits.memory` | Frontend memory limit | `256Mi` |
| `frontend.resources.requests.cpu` | Frontend CPU request | `100m` |
| `frontend.resources.requests.memory` | Frontend memory request | `128Mi` |
| `frontend.autoscaling.enabled` | Enable frontend autoscaling | `false` |
| `frontend.autoscaling.minReplicas` | Minimum frontend replicas | `2` |
| `frontend.autoscaling.maxReplicas` | Maximum frontend replicas | `5` |

### Ingress Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.annotations` | Ingress annotations | `{}` |
| `ingress.hosts` | Ingress hosts configuration | `[]` |
| `ingress.tls` | Ingress TLS configuration | `[]` |

### Monitoring Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `serviceMonitor.enabled` | Enable Prometheus ServiceMonitor | `false` |
| `serviceMonitor.interval` | Scrape interval | `30s` |
| `serviceMonitor.scrapeTimeout` | Scrape timeout | `10s` |

## Examples

See the [examples](./examples/) directory for complete configuration examples:

- [Development](./examples/values-development.yaml) - Minimal configuration for local testing
- [Staging](./examples/values-staging.yaml) - Production-like with reduced resources
- [Production](./examples/values-production.yaml) - Full production configuration with HA

## Upgrading

```bash
# Upgrade to new version
helm upgrade gharts ./helm/gharts \
  -f my-values.yaml \
  --set image.backend.tag=1.1.0 \
  --set image.frontend.tag=1.1.0

# Rollback if needed
helm rollback gharts
```

## Uninstalling

```bash
helm uninstall gharts
```

## Testing

The chart includes Helm tests that verify the deployment:

```bash
helm test gharts
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -l app.kubernetes.io/name=gharts

# Check pod logs
kubectl logs -l app.kubernetes.io/component=backend
kubectl logs -l app.kubernetes.io/component=frontend

# Describe pod for events
kubectl describe pod <pod-name>
```

### Database Connection Issues

```bash
# Check database pod
kubectl get pods -l app.kubernetes.io/name=postgresql

# Check database logs
kubectl logs -l app.kubernetes.io/name=postgresql

# Test database connection
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql postgresql://gharts:PASSWORD@gharts-postgresql:5432/gharts
```

### Ingress Not Working

```bash
# Check ingress status
kubectl get ingress
kubectl describe ingress gharts

# Check ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller
```

## Support

For issues and questions:

- [GitHub Issues](https://github.com/your-org/gha-runner-token-service/issues)
- [Documentation](../../docs/kubernetes_deployment.md)
- [Runbook](../../docs/kubernetes_runbook.md)

## License

See [LICENSE](../../LICENSE) file.