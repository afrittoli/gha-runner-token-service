# GitHub Actions Runner Token Service Helm Chart

This Helm chart deploys the GitHub Actions Runner Token Service to Kubernetes.

## Prerequisites

- Kubernetes 1.24+
- Helm 3.13+
- PostgreSQL database (can be deployed with this chart)
- GitHub App credentials
- OIDC provider configuration

## Installation

### Quick Start

```bash
# Add your values
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

# Install the chart
helm install gharts ./helm/gharts -f my-values.yaml
```

### Using External PostgreSQL

```bash
helm install gharts ./helm/gharts \
  --set postgresql.enabled=false \
  --set config.databaseUrl="postgresql://user:pass@host:5432/dbname"
```

### With Ingress

```bash
helm install gharts ./helm/gharts \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=gharts.example.com \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix
```

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