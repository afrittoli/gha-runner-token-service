# Kubernetes Deployment Guide

This guide covers deploying the GitHub Actions Runner Token Service to Kubernetes using Helm.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Production Deployment](#production-deployment)
- [Monitoring and Operations](#monitoring-and-operations)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

- Kubernetes cluster (1.24+)
- `kubectl` configured to access your cluster
- Helm 3.13+
- Docker or Podman for building images

### Required Resources

- GitHub App credentials (App ID, Private Key)
- OIDC provider configuration (Client ID, Secret, Discovery URL)
- PostgreSQL database (can be deployed with the chart)
- TLS certificate for HTTPS (optional, can use cert-manager)

### Minimum Cluster Resources

- **Development**: 2 CPU cores, 4GB RAM
- **Production**: 4 CPU cores, 8GB RAM (with autoscaling)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/gha-runner-token-service.git
cd gha-runner-token-service
```

### 2. Create a Namespace

```bash
kubectl create namespace gharts
```

### 3. Create Secrets

Create a `secrets.yaml` file with your sensitive configuration:

```yaml
# secrets.yaml
config:
  githubAppId: "123456"
  githubAppPrivateKey: |
    -----BEGIN RSA PRIVATE KEY-----
    Your private key here
    -----END RSA PRIVATE KEY-----
  oidcClientId: "your-oidc-client-id"
  oidcClientSecret: "your-oidc-client-secret"
  oidcDiscoveryUrl: "https://your-oidc-provider/.well-known/openid-configuration"

bootstrap:
  admin:
    password: "change-this-secure-password"
```

### 4. Install the Chart

```bash
helm install gharts ./helm/gharts \
  --namespace gharts \
  --values secrets.yaml \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=gharts.example.com \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix
```

### 5. Verify Installation

```bash
# Check pod status
kubectl get pods -n gharts

# Check services
kubectl get svc -n gharts

# Run Helm tests
helm test gharts -n gharts

# Check logs
kubectl logs -n gharts -l app.kubernetes.io/name=gharts -l app.kubernetes.io/component=backend
```

### 6. Access the Application

```bash
# Port forward for local access
kubectl port-forward -n gharts svc/gharts-frontend 8080:80

# Open browser to http://localhost:8080
```

## Configuration

### Essential Configuration

The following values must be configured for the application to work:

```yaml
# values.yaml
config:
  # GitHub App credentials
  githubAppId: "123456"
  githubAppPrivateKey: "your-private-key"
  
  # OIDC configuration
  oidcClientId: "your-client-id"
  oidcClientSecret: "your-client-secret"
  oidcDiscoveryUrl: "https://provider/.well-known/openid-configuration"
  
  # Database connection (if using external database)
  databaseUrl: "postgresql://user:pass@host:5432/dbname"

# Bootstrap admin account
bootstrap:
  enabled: true
  admin:
    username: "admin"
    password: "secure-password"
    email: "admin@example.com"
```

### Image Configuration

```yaml
image:
  backend:
    repository: ghcr.io/your-org/gha-runner-token-service-backend
    tag: "1.0.0"
    pullPolicy: IfNotPresent
  
  frontend:
    repository: ghcr.io/your-org/gha-runner-token-service-frontend
    tag: "1.0.0"
    pullPolicy: IfNotPresent

imagePullSecrets: []
```

### Database Configuration

#### Using Built-in PostgreSQL

```yaml
postgresql:
  enabled: true
  auth:
    username: gharts
    password: secure-password
    database: gharts
  primary:
    persistence:
      enabled: true
      size: 10Gi
```

#### Using External PostgreSQL

```yaml
postgresql:
  enabled: false

config:
  databaseUrl: "postgresql://user:pass@external-host:5432/dbname"
  databasePoolSize: 20
  databaseMaxOverflow: 10
  databaseSslMode: "require"
```

### Ingress Configuration

#### Using Nginx Ingress

```yaml
ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
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

#### Using Gateway API

```yaml
ingress:
  enabled: false

gateway:
  enabled: true
  gatewayClassName: "istio"
  listeners:
    - name: https
      port: 443
      protocol: HTTPS
      hostname: gharts.example.com
      tls:
        mode: Terminate
        certificateRefs:
          - name: gharts-tls
```

### Autoscaling Configuration

```yaml
backend:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80

frontend:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 5
    targetCPUUtilizationPercentage: 70
```

### Resource Limits

```yaml
backend:
  resources:
    limits:
      cpu: 1000m
      memory: 1Gi
    requests:
      cpu: 500m
      memory: 512Mi

frontend:
  resources:
    limits:
      cpu: 500m
      memory: 256Mi
    requests:
      cpu: 100m
      memory: 128Mi
```

## Production Deployment

### 1. Prepare Production Values

Create a `production-values.yaml` file:

```yaml
# production-values.yaml
replicaCount:
  backend: 3
  frontend: 2

image:
  backend:
    repository: ghcr.io/your-org/gha-runner-token-service-backend
    tag: "1.0.0"
    pullPolicy: IfNotPresent
  frontend:
    repository: ghcr.io/your-org/gha-runner-token-service-frontend
    tag: "1.0.0"
    pullPolicy: IfNotPresent

backend:
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80
  
  resources:
    limits:
      cpu: 2000m
      memory: 2Gi
    requests:
      cpu: 1000m
      memory: 1Gi
  
  podDisruptionBudget:
    enabled: true
    minAvailable: 2

frontend:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
  
  resources:
    limits:
      cpu: 1000m
      memory: 512Mi
    requests:
      cpu: 200m
      memory: 256Mi
  
  podDisruptionBudget:
    enabled: true
    minAvailable: 1

postgresql:
  enabled: false

config:
  databaseUrl: "postgresql://user:pass@prod-db.example.com:5432/gharts"
  databasePoolSize: 50
  databaseMaxOverflow: 20
  databaseSslMode: "require"
  logLevel: "INFO"

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
  hosts:
    - host: gharts.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: gharts-tls
      hosts:
        - gharts.example.com

serviceMonitor:
  enabled: true
  interval: 30s
```

### 2. Deploy to Production

```bash
# Create production namespace
kubectl create namespace gharts-prod

# Create secrets
kubectl create secret generic gharts-secrets \
  --namespace gharts-prod \
  --from-literal=github-app-id="123456" \
  --from-file=github-app-private-key=./github-app-key.pem \
  --from-literal=oidc-client-id="your-client-id" \
  --from-literal=oidc-client-secret="your-client-secret" \
  --from-literal=bootstrap-admin-password="secure-password"

# Install chart
helm install gharts ./helm/gharts \
  --namespace gharts-prod \
  --values production-values.yaml \
  --wait \
  --timeout 10m

# Verify deployment
kubectl get all -n gharts-prod
helm test gharts -n gharts-prod
```

### 3. Post-Deployment Verification

```bash
# Check pod health
kubectl get pods -n gharts-prod -w

# Check logs
kubectl logs -n gharts-prod -l app.kubernetes.io/component=backend --tail=100

# Test endpoints
curl -k https://gharts.example.com/health
curl -k https://gharts.example.com/api/v1/health

# Check metrics (if enabled)
kubectl port-forward -n gharts-prod svc/gharts-backend 8000:8000
curl http://localhost:8000/metrics
```

## Monitoring and Operations

### Health Checks

The application exposes health check endpoints:

- **Backend**: `GET /health` - Returns 200 if healthy
- **Frontend**: `GET /` - Returns 200 if Nginx is serving

### Metrics

If Prometheus monitoring is enabled:

```bash
# Port forward to metrics endpoint
kubectl port-forward -n gharts svc/gharts-backend 8000:8000

# Access metrics
curl http://localhost:8000/metrics
```

### Logging

View application logs:

```bash
# Backend logs
kubectl logs -n gharts -l app.kubernetes.io/component=backend -f

# Frontend logs
kubectl logs -n gharts -l app.kubernetes.io/component=frontend -f

# All logs
kubectl logs -n gharts -l app.kubernetes.io/name=gharts -f --all-containers
```

### Scaling

Manual scaling:

```bash
# Scale backend
kubectl scale deployment gharts-backend -n gharts --replicas=5

# Scale frontend
kubectl scale deployment gharts-frontend -n gharts --replicas=3
```

### Updates and Rollbacks

```bash
# Update to new version
helm upgrade gharts ./helm/gharts \
  --namespace gharts \
  --values production-values.yaml \
  --set image.backend.tag=1.1.0 \
  --set image.frontend.tag=1.1.0

# Check rollout status
kubectl rollout status deployment/gharts-backend -n gharts
kubectl rollout status deployment/gharts-frontend -n gharts

# Rollback if needed
helm rollback gharts -n gharts
```

### Backup and Restore

Backup database:

```bash
# If using built-in PostgreSQL
kubectl exec -n gharts gharts-postgresql-0 -- \
  pg_dump -U gharts gharts > backup.sql

# Restore
kubectl exec -i -n gharts gharts-postgresql-0 -- \
  psql -U gharts gharts < backup.sql
```

## Troubleshooting

### Common Issues

#### Pods Not Starting

```bash
# Check pod status
kubectl describe pod -n gharts <pod-name>

# Check events
kubectl get events -n gharts --sort-by='.lastTimestamp'

# Check logs
kubectl logs -n gharts <pod-name>
```

#### Database Connection Issues

```bash
# Test database connectivity
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql postgresql://user:pass@gharts-postgresql:5432/gharts

# Check database logs
kubectl logs -n gharts gharts-postgresql-0
```

#### Ingress Not Working

```bash
# Check ingress status
kubectl describe ingress -n gharts gharts

# Check ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller

# Test service directly
kubectl port-forward -n gharts svc/gharts-frontend 8080:80
```

#### Authentication Issues

```bash
# Check OIDC configuration
kubectl get configmap -n gharts gharts -o yaml

# Check backend logs for auth errors
kubectl logs -n gharts -l app.kubernetes.io/component=backend | grep -i auth

# Verify OIDC discovery URL
curl https://your-oidc-provider/.well-known/openid-configuration
```

### Debug Mode

Enable debug logging:

```bash
helm upgrade gharts ./helm/gharts \
  --namespace gharts \
  --reuse-values \
  --set config.logLevel=DEBUG
```

### Getting Support

1. Check logs: `kubectl logs -n gharts -l app.kubernetes.io/name=gharts`
2. Check events: `kubectl get events -n gharts`
3. Run diagnostics: `helm test gharts -n gharts`
4. Review configuration: `helm get values gharts -n gharts`

## Security Considerations

### Secrets Management

- Use Kubernetes Secrets or external secret managers (e.g., HashiCorp Vault)
- Enable encryption at rest for Secrets
- Rotate credentials regularly

### Network Policies

```yaml
# Example network policy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: gharts-network-policy
  namespace: gharts
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: gharts
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: ingress-nginx
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: postgresql
      ports:
        - protocol: TCP
          port: 5432
```

### Pod Security

The chart includes security contexts:

- Non-root user execution
- Read-only root filesystem
- Dropped capabilities
- Security context constraints

## Next Steps

- [Configure monitoring](./monitoring.md)
- [Set up backup strategy](./backup.md)
- [Configure high availability](./ha_setup.md)
- [Performance tuning](./performance.md)