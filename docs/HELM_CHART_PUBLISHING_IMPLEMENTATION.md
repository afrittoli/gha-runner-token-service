# Helm Chart Publishing Implementation Summary

This document summarizes the implementation of Helm chart publishing to GitHub Container Registry (GHCR).

## Implementation Date

2026-03-04

## Overview

The Helm chart for the GitHub Actions Runner Token Service is now automatically published to `oci://ghcr.io/afrittoli/gharts` through GitHub Actions workflows.

## Changes Made

### 1. Chart Configuration

**File: `helm/gharts/Chart.yaml`**
- Added OCI-specific annotations for better registry display
- Added comprehensive metadata (title, description, vendor, licenses)
- Enhanced keywords for discoverability

### 2. GitHub Actions Workflows

#### New Workflow: `.github/workflows/helm-chart.yml`
- **Purpose**: Validates Helm chart on every PR and main branch push
- **Jobs**:
  - `lint`: Runs helm lint and template validation
  - `test-deployment`: Deploys to kind cluster and runs helm tests
  - `package`: Packages chart for verification
- **Triggers**: PR and push to main (when helm chart files change)

#### Updated: `.github/workflows/docker-build.yml`
- **Added Job**: `publish-helm-chart`
- **Publishes**: Chart with `main` and `sha-<commit>` tags on main branch pushes
- **Dependencies**: Runs after backend and frontend images are built
- **Authentication**: Uses GITHUB_TOKEN with packages:write permission

#### Updated: `.github/workflows/release.yml`
- **Enhanced Job**: `package-helm-chart`
- **Publishes**: Chart with semantic version tags on releases
- **Tags**: `v1.2.3`, `v1.2`, `v1`, `latest`
- **Also**: Uploads .tgz file to GitHub Release (existing behavior preserved)
- **Updated**: Release notes to include OCI registry installation instructions

### 3. Makefile Targets

**File: `Makefile`**

Added new targets for Helm chart operations:
- `helm-lint`: Lint Helm chart
- `helm-template`: Validate chart templates
- `helm-package`: Package chart to dist/ directory
- `helm-push`: Push chart to OCI registry (requires VERSION)
- `helm-test`: Run all chart tests (lint + template)
- `helm-install-local`: Install chart locally from filesystem
- `helm-uninstall-local`: Uninstall local chart installation
- `helm-install-oci`: Install chart from OCI registry
- `helm-uninstall-oci`: Uninstall OCI chart installation

### 4. Documentation

#### New Documents

1. **`docs/helm_chart_release.md`**
   - Comprehensive release process guide
   - Workflow diagrams (mermaid)
   - Manual release procedures
   - Rollback procedures
   - Troubleshooting guide
   - Best practices checklist

2. **`docs/helm_chart_publishing_plan.md`**
   - Detailed implementation plan
   - Technical specifications
   - Workflow diagrams
   - Security considerations
   - Testing strategy

3. **`docs/helm_chart_publishing_summary.md`**
   - Executive summary
   - Quick overview
   - Implementation checklist

#### Updated Documents

1. **`helm/gharts/README.md`**
   - Added "Installation from OCI Registry" as primary method
   - Added version management table
   - Added multiple installation scenarios
   - Reorganized content for better flow

2. **`README.md`**
   - Added Quick Start section with Kubernetes deployment
   - Added links to Helm chart documentation
   - Added Helm Release Process to documentation links

3. **`docs/kubernetes_deployment.md`**
   - Added "Method 1: Install from OCI Registry (Recommended)"
   - Kept existing methods as alternatives
   - Updated all examples to use OCI registry

4. **`docs/deployment_checklist.md`**
   - Added Kubernetes/Helm deployment as recommended method
   - Kept traditional deployment as alternative

## Publishing Strategy

### Main Branch Pushes

When code is pushed to the `main` branch:
- Chart is published with tags: `main`, `sha-<commit>`
- **Note**: Does NOT include `latest` tag (only releases get `latest`)

### Release Tags

When a release tag (e.g., `v1.2.3`) is created:
- Chart is published with tags: `v1.2.3`, `v1.2`, `v1`, `latest`
- Chart is also uploaded to GitHub Release as `.tgz` file

## Installation Methods

### From OCI Registry (Recommended)

```bash
# Latest stable release
helm install gharts oci://ghcr.io/afrittoli/gharts --version latest

# Specific version
helm install gharts oci://ghcr.io/afrittoli/gharts --version 1.2.3

# From main branch (testing)
helm install gharts oci://ghcr.io/afrittoli/gharts --version main
```

### From GitHub Release

```bash
# Download and install
wget https://github.com/afrittoli/gha-runner-token-service/releases/download/v1.2.3/gharts-1.2.3.tgz
helm install gharts ./gharts-1.2.3.tgz
```

### From Local Chart

```bash
# Clone and install
git clone https://github.com/afrittoli/gha-runner-token-service.git
helm install gharts ./helm/gharts
```

## Testing

### Automated Testing (CI)

Every PR that modifies Helm chart files triggers:
1. Helm lint validation
2. Template rendering validation
3. Deployment to kind cluster
4. Helm test execution
5. Pod startup verification

### Local Testing

```bash
# Run all tests
make helm-test

# Install locally
make helm-install-local

# Clean up
make helm-uninstall-local
```

## Workflow Diagrams

### PR Workflow
```
PR → Helm Chart CI
  ├─ Lint Chart
  ├─ Validate Templates
  ├─ Deploy to Kind
  └─ Run Helm Tests
```

### Main Branch Workflow
```
Push to Main → Docker Build
  ├─ Build Images
  ├─ Push Images: main, sha
  ├─ Package Chart
  └─ Push Chart: main, sha
```

### Release Workflow
```
Tag v1.2.3 → Release Workflow
  ├─ Create GitHub Release
  ├─ Build & Push Images: v1.2.3, v1.2, v1, latest
  ├─ Package Chart
  ├─ Upload to Release
  ├─ Push to GHCR: v1.2.3, v1.2, v1, latest
  └─ Deploy Test
```

## Version Management

| Tag Type | Example | Use Case | Updated On |
|----------|---------|----------|------------|
| Exact | `1.2.3` | Production | Releases only |
| Minor | `1.2` | Auto-update patches | Releases only |
| Major | `1` | Auto-update minor | Releases only |
| Latest | `latest` | Always newest stable | Releases only |
| Branch | `main` | Testing unreleased | Every main push |
| Commit | `sha-abc123` | Testing specific commit | Every main push |

## Security

- **Authentication**: Uses `GITHUB_TOKEN` with `packages: write` permission
- **Visibility**: Chart is public (matches repository visibility)
- **Access Control**: Managed through GitHub repository permissions
- **Future Enhancement**: Consider adding chart signing with cosign

## Rollback Procedure

If a release has issues:

```bash
# Rollback to previous version
helm upgrade gharts oci://ghcr.io/afrittoli/gharts --version 1.2.2

# Or use Helm rollback
helm rollback gharts
```

## Files Modified

### Created (6 files)
1. `.github/workflows/helm-chart.yml` - New CI workflow
2. `docs/helm_chart_release.md` - Release process guide
3. `docs/helm_chart_publishing_plan.md` - Implementation plan
4. `docs/helm_chart_publishing_summary.md` - Executive summary
5. `docs/HELM_CHART_PUBLISHING_IMPLEMENTATION.md` - This file

### Modified (6 files)
1. `helm/gharts/Chart.yaml` - Added OCI annotations
2. `.github/workflows/docker-build.yml` - Added chart publishing
3. `.github/workflows/release.yml` - Enhanced with OCI publishing
4. `Makefile` - Added helm targets
5. `helm/gharts/README.md` - Added OCI installation
6. `README.md` - Added Quick Start
7. `docs/kubernetes_deployment.md` - Added OCI method
8. `docs/deployment_checklist.md` - Added Helm deployment

## Next Steps

### Before First Release

1. **Test the workflows**:
   - Create a test branch
   - Push changes to trigger helm-chart.yml
   - Verify all tests pass

2. **Test chart publishing**:
   - Merge to main
   - Verify chart is published with `main` and `sha-<commit>` tags
   - Test installation from OCI registry

3. **Create a test release**:
   - Tag with `v0.0.1-alpha` or similar
   - Verify all release workflows complete
   - Test installation with version tags

### After First Release

1. **Monitor**:
   - Check GitHub Actions logs
   - Verify chart appears in GitHub Packages
   - Test installation from different environments

2. **Announce**:
   - Update project README with OCI registry info
   - Notify users of new installation method
   - Update any external documentation

3. **Iterate**:
   - Gather feedback
   - Improve workflows based on experience
   - Consider adding chart signing

## Support

For issues or questions:
- [GitHub Issues](https://github.com/afrittoli/gha-runner-token-service/issues)
- [Helm Chart README](../helm/gharts/README.md)
- [Release Process Guide](./helm_chart_release.md)
- [Kubernetes Deployment Guide](./kubernetes_deployment.md)

## References

- [Helm OCI Support](https://helm.sh/docs/topics/registries/)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Helm Best Practices](https://helm.sh/docs/chart_best_practices/)