# Kubernetes Deployment Implementation Plan

**Project:** GHARTS (GitHub Actions Runner Token Service)  
**Document Version:** 1.0  
**Date:** 2026-01-29  
**Status:** Planning Phase

## Executive Summary

This document outlines the implementation plan for containerizing and deploying GHARTS on Kubernetes. The architecture separates frontend (React/Nginx) and backend (FastAPI) into independent deployments for optimal scalability and resource utilization.

**Key Objectives:**
- Containerize application with production-ready Dockerfiles
- Create Helm chart for Kubernetes deployment
- Support cloud-managed databases (PostgreSQL RDS/Aurora)
- Implement CI/CD for automated builds and releases
- Enable local testing with Podman and kind/minikube

**Timeline:** 10 phases, estimated 2-3 weeks for full implementation

---

## Architecture Overview

### Deployment Model

**Separate Frontend/Backend Architecture:**
```
┌─────────────────────────────────────┐
│      Frontend Pod (Nginx)           │
│  ┌──────────────────────────────┐  │
│  │   Nginx                      │  │
│  │   - Serves React SPA         │  │
│  │   - Proxies /api to backend  │  │
│  │   - Static asset caching     │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         └─── Backend Service

┌─────────────────────────────────────┐
│      Backend Pod (FastAPI)          │
│  ┌──────────────────────────────┐  │
│  │   FastAPI + Uvicorn          │  │
│  │   - API endpoints only       │  │
│  │   - Business logic           │  │
│  │   - Database access          │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         ├─── PostgreSQL (RDS/Aurora)
         └─── GitHub API
```

### Container Images

1. **Backend Image:** `ghcr.io/[org]/gharts-backend:v1.0.0`
   - Python 3.11 slim base
   - FastAPI + Uvicorn
   - Multi-architecture (amd64, arm64)

2. **Frontend Image:** `ghcr.io/[org]/gharts-frontend:v1.0.0`
   - Nginx alpine base
   - React SPA build artifacts
   - Multi-architecture (amd64, arm64)

### Scaling Strategy

- **Frontend:** Scale based on HTTP requests, static content delivery
- **Backend:** Scale based on API processing, database connections
- **Recommended Ratio:** 2-3 frontend pods per backend pod

---

## Implementation Phases

### Phase 1: Remove Legacy Dashboard and Prepare Codebase ✓

**Priority:** High | **Effort:** 2-3 hours

Remove monolithic dashboard serving from FastAPI to prepare for separate frontend deployment.

**Files to Modify:**
- `app/main.py` - Remove static file mounting and template rendering
- `app/templates/dashboard.html` - Delete legacy template
- `requirements.txt` - Remove Jinja2 if no longer needed
- Tests - Update to reflect API-only backend

**Success Criteria:**
- No HTML templates in backend
- All API endpoints functional
- Backend serves only JSON responses

---

### Phase 2: Create Backend Dockerfile ✓

**Priority:** High | **Effort:** 4-6 hours

Create production-ready backend container with security best practices.

**New Files:**
- `Dockerfile.backend` - Multi-stage build
- `.dockerignore` - Exclude unnecessary files

**Key Features:**
- Non-root user (uid 1000)
- Read-only root filesystem
- Health check endpoint
- Multi-architecture support
- Optimized layer caching

**Test Command:**
```bash
podman build -f Dockerfile.backend -t gharts-backend:latest .
```

---

### Phase 3: Create Frontend Dockerfile ✓

**Priority:** High | **Effort:** 4-6 hours

Create optimized frontend container with Nginx.

**New Files:**
- `frontend/Dockerfile` - Multi-stage build
- `frontend/nginx.conf` - Nginx configuration
- `frontend/.dockerignore` - Exclude unnecessary files

**Nginx Features:**
- SPA routing support
- API proxy to backend
- Security headers
- Gzip compression
- Static asset caching

**Test Command:**
```bash
podman build -f frontend/Dockerfile -t gharts-frontend:latest ./frontend
```

---

### Phase 4: Database Configuration ✓

**Priority:** High | **Effort:** 3-4 hours

Ensure compatibility with cloud-managed PostgreSQL.

**Files to Modify:**
- `app/database.py` - Add PostgreSQL support, connection pooling, SSL/TLS
- `app/config.py` - Parse PostgreSQL connection strings
- `requirements.txt` - Add psycopg2-binary

**New Files:**
- `alembic.ini` - Migration configuration
- Migration scripts for SQLite → PostgreSQL

**Success Criteria:**
- PostgreSQL connectivity works
- SSL/TLS connections supported
- Connection pooling configured
- SQLite still works for local dev

---

### Phase 5: Bootstrap Admin Account ✓

**Priority:** High | **Effort:** 3-4 hours

Automatically create initial admin user on first deployment.

**New Files:**
- `app/bootstrap.py` - Bootstrap logic

**Files to Modify:**
- `app/main.py` - Add startup event for bootstrap
- `app/config.py` - Add bootstrap environment variables

**Environment Variables:**
- `BOOTSTRAP_ADMIN_USERNAME` (default: "admin")
- `BOOTSTRAP_ADMIN_PASSWORD` (required)
- `BOOTSTRAP_ADMIN_EMAIL` (optional)

**Success Criteria:**
- Admin user created on first run
- Idempotent operation
- Password securely hashed
- Audit log entry created

---

### Phase 6: Helm Chart Structure ✓

**Priority:** High | **Effort:** 8-12 hours

Create production-ready Helm chart.

**Directory Structure:**
```
helm/gharts/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── backend-deployment.yaml
│   ├── frontend-deployment.yaml
│   ├── backend-service.yaml
│   ├── frontend-service.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── gateway.yaml
│   ├── httproute.yaml
│   ├── backend-hpa.yaml
│   ├── frontend-hpa.yaml
│   ├── pdb.yaml
│   ├── serviceaccount.yaml
│   └── NOTES.txt
└── examples/
    ├── values-local.yaml
    ├── values-dev.yaml
    ├── values-prod.yaml
    ├── values-aws.yaml
    └── values-gcp.yaml
```

**Success Criteria:**
- `helm lint` passes
- `helm template` renders correctly
- All required resources included
- Example configurations provided

---

### Phase 7: CI/CD Workflows ✓

**Priority:** Medium | **Effort:** 6-8 hours

Automate container builds and releases.

**New Files:**
- `.github/workflows/docker-build-test.yml` - PR testing
- `.github/workflows/release.yml` - Release automation

**Features:**
- Multi-architecture builds (amd64, arm64)
- Security scanning with Trivy
- Push to GitHub Container Registry
- Semantic versioning
- Automated release notes
- Helm chart packaging

**Success Criteria:**
- PR builds test images
- Security scanning runs
- Release workflow publishes images
- Helm chart attached to releases

---

### Phase 8: Documentation ✓

**Priority:** Medium | **Effort:** 4-6 hours

Comprehensive deployment guides and examples.

**New Files:**
- `docs/kubernetes_deployment.md` - Main deployment guide
- `docs/migration_guide.md` - Migration procedures
- `docs/runbooks/deployment.md` - Deployment procedures
- `docs/runbooks/upgrade.md` - Upgrade procedures
- `docs/runbooks/rollback.md` - Rollback procedures
- `docs/runbooks/troubleshooting.md` - Common issues

**Success Criteria:**
- Quick start guide tested
- Example configurations validated
- Troubleshooting guide comprehensive
- Runbooks actionable

---

### Phase 9: Podman Testing ✓

**Priority:** High | **Effort:** 4-6 hours

Validate containers with Podman before Kubernetes deployment.

**New Files:**
- `Makefile` - Build and test targets
- `scripts/test-containers.sh` - Container testing
- `scripts/load-to-kind.sh` - Load images to kind

**Test Scenarios:**
- Build with Podman
- Run containers locally
- Test with Podman pod
- Export images for kind
- Multi-architecture builds

**Success Criteria:**
- Images build with Podman
- Containers run as non-root
- Health checks pass
- Images load into kind

---

### Phase 10: Kubernetes Validation ✓

**Priority:** High | **Effort:** 6-8 hours

Test Helm chart in local Kubernetes cluster.

**New Files:**
- `scripts/setup-kind-cluster.sh` - Create kind cluster
- `scripts/deploy-to-kind.sh` - Deploy to kind
- `kind-config.yaml` - kind configuration
- `scripts/setup-minikube.sh` - Alternative for minikube

**Validation Checklist:**
- [ ] Cluster created successfully
- [ ] Images loaded into cluster
- [ ] Helm chart deploys without errors
- [ ] All pods running and ready
- [ ] Services accessible
- [ ] Frontend loads in browser
- [ ] API endpoints respond
- [ ] Database connectivity works
- [ ] Bootstrap admin created
- [ ] Helm upgrade/rollback works

**Success Criteria:**
- All validation checklist items pass
- Deployment documented
- Issues identified and resolved

---

## File Inventory

### Files to Create

**Dockerfiles:**
- `Dockerfile.backend` - Backend container
- `frontend/Dockerfile` - Frontend container
- `.dockerignore` - Backend ignore rules
- `frontend/.dockerignore` - Frontend ignore rules

**Helm Chart:**
- `helm/gharts/Chart.yaml`
- `helm/gharts/values.yaml`
- `helm/gharts/templates/_helpers.tpl`
- `helm/gharts/templates/backend-deployment.yaml`
- `helm/gharts/templates/frontend-deployment.yaml`
- `helm/gharts/templates/backend-service.yaml`
- `helm/gharts/templates/frontend-service.yaml`
- `helm/gharts/templates/configmap.yaml`
- `helm/gharts/templates/secret.yaml`
- `helm/gharts/templates/gateway.yaml`
- `helm/gharts/templates/httproute.yaml`
- `helm/gharts/templates/backend-hpa.yaml`
- `helm/gharts/templates/frontend-hpa.yaml`
- `helm/gharts/templates/pdb.yaml`
- `helm/gharts/templates/serviceaccount.yaml`
- `helm/gharts/templates/NOTES.txt`
- `helm/gharts/examples/values-local.yaml`
- `helm/gharts/examples/values-dev.yaml`
- `helm/gharts/examples/values-prod.yaml`
- `helm/gharts/examples/values-aws.yaml`
- `helm/gharts/examples/values-gcp.yaml`

**CI/CD:**
- `.github/workflows/docker-build-test.yml`
- `.github/workflows/release.yml`

**Scripts:**
- `Makefile`
- `scripts/test-containers.sh`
- `scripts/load-to-kind.sh`
- `scripts/setup-kind-cluster.sh`
- `scripts/deploy-to-kind.sh`
- `scripts/setup-minikube.sh`
- `kind-config.yaml`

**Documentation:**
- `docs/kubernetes_deployment.md`
- `docs/migration_guide.md`
- `docs/runbooks/deployment.md`
- `docs/runbooks/upgrade.md`
- `docs/runbooks/rollback.md`
- `docs/runbooks/troubleshooting.md`

**Application Code:**
- `app/bootstrap.py`
- `frontend/nginx.conf`
- `alembic.ini` (if not exists)

### Files to Modify

- `app/main.py` - Remove dashboard, add bootstrap
- `app/database.py` - Add PostgreSQL support
- `app/config.py` - Add bootstrap and database config
- `requirements.txt` - Add psycopg2-binary
- Tests - Update for API-only backend

### Files to Delete

- `app/templates/dashboard.html` - Legacy template

---

## Dependencies and Prerequisites

### Development Environment
- Podman (for container builds)
- kind or minikube (for local Kubernetes)
- kubectl (Kubernetes CLI)
- Helm 3.x (package manager)
- Python 3.11+ (for backend development)
- Node.js 18+ (for frontend development)

### Cloud Resources (Production)
- Kubernetes cluster (EKS, GKE, AKS, etc.)
- PostgreSQL database (RDS, Aurora, Cloud SQL, etc.)
- Container registry (GitHub Container Registry)
- DNS and TLS certificates
- GitHub App credentials

### Python Packages (New)
- `psycopg2-binary` - PostgreSQL driver
- `alembic` - Database migrations (if not present)

---

## Risk Assessment

### High Risk Items

**Database Migration**
- **Risk:** Data loss during SQLite → PostgreSQL migration
- **Mitigation:** 
  - Create backup before migration
  - Test migration in staging
  - Document rollback procedure
  - Maintain SQLite support for local dev

**Downtime During Deployment**
- **Risk:** Service interruption during initial deployment
- **Mitigation:**
  - Use blue-green deployment
  - Implement proper health checks
  - Configure pod disruption budgets
  - Test rollback procedures

### Medium Risk Items

**Configuration Complexity**
- **Risk:** Misconfiguration leading to deployment failures
- **Mitigation:**
  - Provide sensible defaults
  - Create example configurations
  - Document all options
  - Validate in CI

**Secret Management**
- **Risk:** Secrets exposed or improperly managed
- **Mitigation:**
  - Use Kubernetes Secrets
  - Never commit secrets to git
  - Document secret creation
  - Consider external secrets operator

### Low Risk Items

**Container Build Issues**
- **Risk:** Build failures or large image sizes
- **Mitigation:**
  - Multi-stage builds
  - Layer caching
  - Regular testing
  - Size monitoring

---

## Success Metrics

### Technical Metrics
- ✅ All containers build successfully
- ✅ Image sizes optimized (<200MB backend, <50MB frontend)
- ✅ All tests pass
- ✅ Security scans show no critical vulnerabilities
- ✅ Helm chart validates and deploys
- ✅ Application accessible and functional

### Operational Metrics
- ✅ Deployment time < 5 minutes
- ✅ Zero-downtime upgrades
- ✅ Rollback time < 2 minutes
- ✅ Pod startup time < 30 seconds
- ✅ Health checks respond < 1 second

### Documentation Metrics
- ✅ Quick start guide complete
- ✅ All configuration options documented
- ✅ Troubleshooting guide comprehensive
- ✅ Runbooks actionable
- ✅ Examples tested and validated

---

## Timeline Estimate

| Phase | Description | Effort | Dependencies |
|-------|-------------|--------|--------------|
| 1 | Remove legacy dashboard | 2-3 hours | None |
| 2 | Backend Dockerfile | 4-6 hours | Phase 1 |
| 3 | Frontend Dockerfile | 4-6 hours | None |
| 4 | Database configuration | 3-4 hours | Phase 2 |
| 5 | Bootstrap admin | 3-4 hours | Phase 4 |
| 6 | Helm chart | 8-12 hours | Phases 2, 3 |
| 7 | CI/CD workflows | 6-8 hours | Phases 2, 3, 6 |
| 8 | Documentation | 4-6 hours | All phases |
| 9 | Podman testing | 4-6 hours | Phases 2, 3 |
| 10 | K8s validation | 6-8 hours | Phases 6, 9 |

**Total Estimated Effort:** 44-63 hours (approximately 2-3 weeks)

---

## Next Steps

1. **Review and Approve Plan**
   - Stakeholder review
   - Technical review
   - Security review

2. **Begin Implementation**
   - Start with Phase 1
   - Work sequentially through phases
   - Test after each phase

3. **Continuous Testing**
   - Test locally with Podman
   - Test in kind/minikube
   - Validate in staging environment

4. **Production Deployment**
   - Deploy to production cluster
   - Monitor closely
   - Document lessons learned

---

## References

- [Design Document](docs/design/kubernetes_deployment.md) - Original design specification
- [Helm Documentation](https://helm.sh/docs/) - Helm best practices
- [Gateway API](https://gateway-api.sigs.k8s.io/) - Gateway API specification
- [Podman Documentation](https://docs.podman.io/) - Podman usage guide
- [kind Documentation](https://kind.sigs.k8s.io/) - kind usage guide

---

## Appendix: Quick Reference Commands

### Podman Commands
```bash
# Build images
make build-all

# Test containers
make test-backend
make test-frontend

# Load to kind
./scripts/load-to-kind.sh
```

### kind Commands
```bash
# Create cluster
./scripts/setup-kind-cluster.sh

# Deploy application
./scripts/deploy-to-kind.sh

# Delete cluster
kind delete cluster --name gharts-test
```

### Helm Commands
```bash
# Lint chart
helm lint ./helm/gharts

# Template chart
helm template gharts ./helm/gharts

# Install chart
helm install gharts ./helm/gharts -f values.yaml

# Upgrade chart
helm upgrade gharts ./helm/gharts -f values.yaml

# Rollback
helm rollback gharts

# Uninstall
helm uninstall gharts
```

### kubectl Commands
```bash
# Get all resources
kubectl get all -n gharts

# View logs
kubectl logs -l app.kubernetes.io/name=gharts -n gharts

# Port forward
kubectl port-forward -n gharts svc/gharts-frontend 8080:8080

# Describe pod
kubectl describe pod <pod-name> -n gharts

# Execute command in pod
kubectl exec -it <pod-name> -n gharts -- /bin/sh
```

---

**Document Status:** Complete  
**Last Updated:** 2026-01-29  
**Next Review:** After Phase 5 completion
