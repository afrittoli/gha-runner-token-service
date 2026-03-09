# Metrics Endpoint Security

## Overview

The `/metrics` endpoint exposes Prometheus metrics for monitoring the GHARTS service. This document describes security considerations and best practices.

## Endpoint Details

- **Path**: `/metrics`
- **Method**: GET
- **Authentication**: None (by design)
- **Content-Type**: `text/plain; version=0.0.4`

## Security Considerations

### 1. No Authentication Required

The `/metrics` endpoint intentionally does **not** require authentication. This is standard practice for Prometheus metrics endpoints because:

- Prometheus scrapers typically don't support authentication
- Metrics are aggregated statistics, not sensitive data
- Network-level access control is the recommended approach

### 2. Information Disclosure

The metrics endpoint exposes operational information:

**Low Risk Metrics:**
- Request counts and durations
- Runner counts by status
- Sync operation statistics
- Database connection pool stats

**Medium Risk Metrics:**
- GitHub API rate limit remaining
- Hostnames of worker pods
- Error counts by type

**Not Exposed:**
- User credentials or tokens
- Runner registration tokens
- GitHub App private keys
- Database credentials
- Specific user identities

### 3. Recommended Security Controls

#### Network-Level Access Control

**Kubernetes NetworkPolicy** (Recommended):
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: gharts-metrics-policy
spec:
  podSelector:
    matchLabels:
      app: gharts
  policyTypes:
  - Ingress
  ingress:
  # Allow Prometheus scraper
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 8000
  # Allow API traffic from ingress
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
```

**Ingress Configuration**:
```yaml
# Do NOT expose /metrics through public ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: gharts-public
  annotations:
    # Block /metrics path
    nginx.ingress.kubernetes.io/configuration-snippet: |
      location /metrics {
        deny all;
        return 404;
      }
spec:
  rules:
  - host: gharts.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: gharts-backend
            port:
              number: 8000
```

#### Service Mesh (Optional)

If using Istio or Linkerd:
```yaml
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: gharts-metrics-policy
spec:
  selector:
    matchLabels:
      app: gharts
  action: ALLOW
  rules:
  # Allow Prometheus from monitoring namespace
  - from:
    - source:
        namespaces: ["monitoring"]
    to:
    - operation:
        paths: ["/metrics"]
```

### 4. Monitoring Best Practices

1. **Scrape Interval**: Use 15-30 second intervals (Prometheus default)
2. **Retention**: Keep metrics for 15-30 days
3. **Alerting**: Set up alerts for:
   - High error rates
   - Sync failures
   - GitHub API rate limit exhaustion
   - Leader election failures

### 5. Compliance Considerations

**GDPR/Privacy:**
- Metrics do not contain personal data
- Hostnames are operational data, not personal identifiers
- No user tracking or profiling

**SOC 2:**
- Metrics support availability and monitoring controls
- Access control via network policies demonstrates security
- Audit logs track who accesses the service (not metrics)

## Implementation Status

✅ Metrics endpoint implemented (`/metrics`)
✅ No sensitive data exposed
✅ Structured for Prometheus scraping
⚠️ Network-level access control must be configured by operator
⚠️ Ingress should block public access to `/metrics`

## References

- [Prometheus Security Best Practices](https://prometheus.io/docs/operating/security/)
- [Kubernetes NetworkPolicy](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [GHARTS Kubernetes Deployment Guide](../kubernetes_deployment.md)