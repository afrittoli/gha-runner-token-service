# Kubernetes Operations Runbook

This runbook provides step-by-step procedures for common operational tasks.

## Table of Contents

- [Deployment Procedures](#deployment-procedures)
- [Scaling Operations](#scaling-operations)
- [Backup and Restore](#backup-and-restore)
- [Troubleshooting](#troubleshooting)
- [Emergency Procedures](#emergency-procedures)
- [Maintenance Tasks](#maintenance-tasks)

## Deployment Procedures

### Initial Deployment

```bash
# 1. Create namespace
kubectl create namespace gharts-prod

# 2. Create secrets
kubectl create secret generic gharts-secrets \
  --namespace gharts-prod \
  --from-literal=github-app-id="YOUR_APP_ID" \
  --from-file=github-app-private-key=./github-app-key.pem \
  --from-literal=oidc-client-id="YOUR_CLIENT_ID" \
  --from-literal=oidc-client-secret="YOUR_CLIENT_SECRET" \
  --from-literal=bootstrap-admin-password="SECURE_PASSWORD"

# 3. Install Helm chart
helm install gharts ./helm/gharts \
  --namespace gharts-prod \
  --values helm/gharts/examples/values-production.yaml \
  --wait \
  --timeout 10m

# 4. Verify deployment
kubectl get all -n gharts-prod
helm test gharts -n gharts-prod

# 5. Check logs
kubectl logs -n gharts-prod -l app.kubernetes.io/component=backend --tail=50
kubectl logs -n gharts-prod -l app.kubernetes.io/component=frontend --tail=50
```

### Upgrading to New Version

```bash
# 1. Check current version
helm list -n gharts-prod

# 2. Review changes
helm diff upgrade gharts ./helm/gharts \
  --namespace gharts-prod \
  --values helm/gharts/examples/values-production.yaml \
  --set image.backend.tag=NEW_VERSION \
  --set image.frontend.tag=NEW_VERSION

# 3. Perform upgrade
helm upgrade gharts ./helm/gharts \
  --namespace gharts-prod \
  --values helm/gharts/examples/values-production.yaml \
  --set image.backend.tag=NEW_VERSION \
  --set image.frontend.tag=NEW_VERSION \
  --wait \
  --timeout 10m

# 4. Monitor rollout
kubectl rollout status deployment/gharts-backend -n gharts-prod
kubectl rollout status deployment/gharts-frontend -n gharts-prod

# 5. Verify health
kubectl get pods -n gharts-prod
curl -k https://gharts.example.com/health
```

### Rolling Back

```bash
# 1. Check release history
helm history gharts -n gharts-prod

# 2. Rollback to previous version
helm rollback gharts -n gharts-prod

# Or rollback to specific revision
helm rollback gharts REVISION -n gharts-prod

# 3. Verify rollback
kubectl get pods -n gharts-prod -w
helm status gharts -n gharts-prod
```

## Scaling Operations

### Manual Scaling

```bash
# Scale backend
kubectl scale deployment gharts-backend -n gharts-prod --replicas=5

# Scale frontend
kubectl scale deployment gharts-frontend -n gharts-prod --replicas=3

# Verify scaling
kubectl get pods -n gharts-prod -l app.kubernetes.io/component=backend
kubectl get pods -n gharts-prod -l app.kubernetes.io/component=frontend
```

### Adjusting Autoscaling

```bash
# Update HPA settings
helm upgrade gharts ./helm/gharts \
  --namespace gharts-prod \
  --reuse-values \
  --set backend.autoscaling.minReplicas=5 \
  --set backend.autoscaling.maxReplicas=30 \
  --set backend.autoscaling.targetCPUUtilizationPercentage=60

# Check HPA status
kubectl get hpa -n gharts-prod
kubectl describe hpa gharts-backend -n gharts-prod
```

### Handling Traffic Spikes

```bash
# 1. Quickly scale up
kubectl scale deployment gharts-backend -n gharts-prod --replicas=10

# 2. Monitor resource usage
kubectl top pods -n gharts-prod

# 3. Check application metrics
kubectl port-forward -n gharts-prod svc/gharts-backend 8000:8000
curl http://localhost:8000/metrics

# 4. Review logs for errors
kubectl logs -n gharts-prod -l app.kubernetes.io/component=backend --tail=100 | grep ERROR
```

## Backup and Restore

### Database Backup

```bash
# Backup built-in PostgreSQL
kubectl exec -n gharts-prod gharts-postgresql-0 -- \
  pg_dump -U gharts gharts | gzip > backup-$(date +%Y%m%d-%H%M%S).sql.gz

# Backup to S3 (if configured)
kubectl exec -n gharts-prod gharts-postgresql-0 -- \
  pg_dump -U gharts gharts | \
  aws s3 cp - s3://your-bucket/backups/gharts-$(date +%Y%m%d-%H%M%S).sql
```

### Database Restore

```bash
# Restore from backup file
gunzip < backup-20260129-120000.sql.gz | \
  kubectl exec -i -n gharts-prod gharts-postgresql-0 -- \
  psql -U gharts gharts

# Restore from S3
aws s3 cp s3://your-bucket/backups/gharts-20260129-120000.sql - | \
  kubectl exec -i -n gharts-prod gharts-postgresql-0 -- \
  psql -U gharts gharts
```

### Configuration Backup

```bash
# Backup Helm values
helm get values gharts -n gharts-prod > values-backup-$(date +%Y%m%d).yaml

# Backup secrets
kubectl get secret gharts-secrets -n gharts-prod -o yaml > secrets-backup-$(date +%Y%m%d).yaml

# Backup all resources
kubectl get all -n gharts-prod -o yaml > resources-backup-$(date +%Y%m%d).yaml
```

## Troubleshooting

### Pod Not Starting

```bash
# 1. Check pod status
kubectl get pods -n gharts-prod
kubectl describe pod POD_NAME -n gharts-prod

# 2. Check events
kubectl get events -n gharts-prod --sort-by='.lastTimestamp' | tail -20

# 3. Check logs
kubectl logs POD_NAME -n gharts-prod
kubectl logs POD_NAME -n gharts-prod --previous  # Previous container logs

# 4. Check resource constraints
kubectl top pods -n gharts-prod
kubectl describe nodes | grep -A 5 "Allocated resources"

# 5. Check image pull
kubectl get events -n gharts-prod | grep -i "pull"
```

### Database Connection Issues

```bash
# 1. Test database connectivity
kubectl run -it --rm debug --image=postgres:15 --restart=Never -n gharts-prod -- \
  psql postgresql://gharts:PASSWORD@gharts-postgresql:5432/gharts

# 2. Check database pod
kubectl get pods -n gharts-prod -l app.kubernetes.io/name=postgresql
kubectl logs -n gharts-prod gharts-postgresql-0

# 3. Check database service
kubectl get svc -n gharts-prod gharts-postgresql
kubectl describe svc -n gharts-prod gharts-postgresql

# 4. Verify connection string
kubectl get configmap -n gharts-prod gharts -o yaml | grep -i database
```

### High Memory/CPU Usage

```bash
# 1. Check resource usage
kubectl top pods -n gharts-prod
kubectl top nodes

# 2. Check HPA status
kubectl get hpa -n gharts-prod
kubectl describe hpa gharts-backend -n gharts-prod

# 3. Review application metrics
kubectl port-forward -n gharts-prod svc/gharts-backend 8000:8000
curl http://localhost:8000/metrics | grep -E "(memory|cpu)"

# 4. Check for memory leaks
kubectl logs -n gharts-prod -l app.kubernetes.io/component=backend | grep -i "memory"

# 5. Restart pods if needed
kubectl rollout restart deployment/gharts-backend -n gharts-prod
```

### Ingress Not Working

```bash
# 1. Check ingress status
kubectl get ingress -n gharts-prod
kubectl describe ingress gharts -n gharts-prod

# 2. Check ingress controller
kubectl get pods -n ingress-nginx
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=50

# 3. Test service directly
kubectl port-forward -n gharts-prod svc/gharts-frontend 8080:80
curl http://localhost:8080

# 4. Check DNS resolution
nslookup gharts.example.com

# 5. Check TLS certificate
kubectl get certificate -n gharts-prod
kubectl describe certificate gharts-tls -n gharts-prod
```

### Authentication Failures

```bash
# 1. Check OIDC configuration
kubectl get configmap -n gharts-prod gharts -o yaml | grep -i oidc

# 2. Test OIDC discovery
curl https://your-oidc-provider/.well-known/openid-configuration

# 3. Check backend logs for auth errors
kubectl logs -n gharts-prod -l app.kubernetes.io/component=backend | grep -i "auth\|oidc"

# 4. Verify secrets
kubectl get secret -n gharts-prod gharts-secrets -o yaml

# 5. Test authentication flow
curl -v https://gharts.example.com/api/v1/auth/login
```

## Emergency Procedures

### Complete Service Outage

```bash
# 1. Check cluster health
kubectl get nodes
kubectl get pods --all-namespaces | grep -v Running

# 2. Check application pods
kubectl get pods -n gharts-prod

# 3. Check recent events
kubectl get events -n gharts-prod --sort-by='.lastTimestamp' | tail -50

# 4. Scale up if needed
kubectl scale deployment gharts-backend -n gharts-prod --replicas=5
kubectl scale deployment gharts-frontend -n gharts-prod --replicas=3

# 5. Restart deployments
kubectl rollout restart deployment/gharts-backend -n gharts-prod
kubectl rollout restart deployment/gharts-frontend -n gharts-prod

# 6. Monitor recovery
kubectl get pods -n gharts-prod -w
```

### Database Corruption

```bash
# 1. Stop application pods
kubectl scale deployment gharts-backend -n gharts-prod --replicas=0

# 2. Backup current state
kubectl exec -n gharts-prod gharts-postgresql-0 -- \
  pg_dump -U gharts gharts > emergency-backup-$(date +%Y%m%d-%H%M%S).sql

# 3. Restore from last good backup
gunzip < last-good-backup.sql.gz | \
  kubectl exec -i -n gharts-prod gharts-postgresql-0 -- \
  psql -U gharts gharts

# 4. Verify database
kubectl exec -it -n gharts-prod gharts-postgresql-0 -- \
  psql -U gharts gharts -c "SELECT COUNT(*) FROM users;"

# 5. Restart application
kubectl scale deployment gharts-backend -n gharts-prod --replicas=3
```

### Security Incident

```bash
# 1. Isolate affected pods
kubectl label pod POD_NAME -n gharts-prod quarantine=true
kubectl annotate pod POD_NAME -n gharts-prod incident="security-$(date +%Y%m%d)"

# 2. Collect logs
kubectl logs POD_NAME -n gharts-prod > incident-logs-$(date +%Y%m%d-%H%M%S).log

# 3. Rotate secrets
kubectl delete secret gharts-secrets -n gharts-prod
kubectl create secret generic gharts-secrets \
  --namespace gharts-prod \
  --from-literal=github-app-id="NEW_APP_ID" \
  --from-file=github-app-private-key=./new-github-app-key.pem \
  --from-literal=oidc-client-id="NEW_CLIENT_ID" \
  --from-literal=oidc-client-secret="NEW_CLIENT_SECRET" \
  --from-literal=bootstrap-admin-password="NEW_SECURE_PASSWORD"

# 4. Restart all pods
kubectl rollout restart deployment/gharts-backend -n gharts-prod
kubectl rollout restart deployment/gharts-frontend -n gharts-prod

# 5. Review audit logs
kubectl logs -n gharts-prod -l app.kubernetes.io/component=backend | grep -i "audit"
```

## Maintenance Tasks

### Certificate Renewal

```bash
# 1. Check certificate expiry
kubectl get certificate -n gharts-prod
kubectl describe certificate gharts-tls -n gharts-prod

# 2. Force renewal (if using cert-manager)
kubectl delete certificate gharts-tls -n gharts-prod
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: gharts-tls
  namespace: gharts-prod
spec:
  secretName: gharts-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
    - gharts.example.com
EOF

# 3. Verify new certificate
kubectl get certificate -n gharts-prod -w
```

### Log Rotation

```bash
# 1. Check log sizes
kubectl exec -n gharts-prod POD_NAME -- du -sh /var/log

# 2. Archive old logs
kubectl exec -n gharts-prod POD_NAME -- \
  tar czf /tmp/logs-$(date +%Y%m%d).tar.gz /var/log/*.log

# 3. Clear old logs
kubectl exec -n gharts-prod POD_NAME -- \
  find /var/log -name "*.log" -mtime +7 -delete
```

### Database Maintenance

```bash
# 1. Vacuum database
kubectl exec -n gharts-prod gharts-postgresql-0 -- \
  psql -U gharts gharts -c "VACUUM ANALYZE;"

# 2. Check database size
kubectl exec -n gharts-prod gharts-postgresql-0 -- \
  psql -U gharts gharts -c "SELECT pg_size_pretty(pg_database_size('gharts'));"

# 3. Check table sizes
kubectl exec -n gharts-prod gharts-postgresql-0 -- \
  psql -U gharts gharts -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# 4. Reindex if needed
kubectl exec -n gharts-prod gharts-postgresql-0 -- \
  psql -U gharts gharts -c "REINDEX DATABASE gharts;"
```

### Updating Configuration

```bash
# 1. Update ConfigMap
kubectl edit configmap gharts -n gharts-prod

# 2. Restart pods to pick up changes
kubectl rollout restart deployment/gharts-backend -n gharts-prod

# 3. Verify new configuration
kubectl get configmap gharts -n gharts-prod -o yaml
kubectl logs -n gharts-prod -l app.kubernetes.io/component=backend --tail=20
```

### Health Checks

```bash
# Daily health check script
#!/bin/bash
NAMESPACE="gharts-prod"

echo "=== Pod Status ==="
kubectl get pods -n $NAMESPACE

echo -e "\n=== Resource Usage ==="
kubectl top pods -n $NAMESPACE

echo -e "\n=== HPA Status ==="
kubectl get hpa -n $NAMESPACE

echo -e "\n=== Recent Events ==="
kubectl get events -n $NAMESPACE --sort-by='.lastTimestamp' | tail -10

echo -e "\n=== Application Health ==="
curl -s https://gharts.example.com/health | jq .

echo -e "\n=== Database Connection ==="
kubectl exec -n $NAMESPACE gharts-postgresql-0 -- \
  psql -U gharts gharts -c "SELECT 1;" > /dev/null && echo "OK" || echo "FAILED"
```

## Monitoring and Alerts

### Key Metrics to Monitor

- Pod restart count
- CPU and memory usage
- Request latency
- Error rate
- Database connection pool usage
- Disk usage (for PostgreSQL)

### Setting Up Alerts

```yaml
# Example PrometheusRule
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: gharts-alerts
  namespace: gharts-prod
spec:
  groups:
    - name: gharts
      interval: 30s
      rules:
        - alert: HighErrorRate
          expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High error rate detected"
        
        - alert: PodRestartingTooOften
          expr: rate(kube_pod_container_status_restarts_total[15m]) > 0
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Pod is restarting frequently"
```

## Contact Information

- **On-Call Engineer**: [Your contact info]
- **Escalation**: [Manager contact info]
- **Vendor Support**: [Support contact if applicable]

## Additional Resources

- [Kubernetes Deployment Guide](./kubernetes_deployment.md)
- [Application Documentation](./README.md)
- [Helm Chart Documentation](../helm/gharts/README.md)