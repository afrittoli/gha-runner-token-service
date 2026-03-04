# CI/CD Workflows

This document describes the continuous integration and deployment workflows for the GitHub Actions Runner Token Service.

## Overview

The project uses GitHub Actions for CI/CD with the following workflows:

- [**backend.yaml**](../.github/workflows/backend.yaml) - Backend tests and linting
- [**frontend.yml**](../.github/workflows/frontend.yml) - Frontend tests, linting, and build
- [**helm-chart.yml**](../.github/workflows/helm-chart.yml) - Helm chart validation
- [**docker-build.yml**](../.github/workflows/docker-build.yml) - Build images, test Helm deployment, publish artifacts
- [**release.yml**](../.github/workflows/release.yml) - Create releases and publish versioned artifacts

## Workflow Diagrams

### Pull Request Flow

When a pull request is created or updated, multiple workflows run in parallel:

```mermaid
graph TB
    PR[Pull Request Created/Updated]

    subgraph "Parallel Workflows"
        subgraph "backend.yaml"
            B1[Backend Tests]
        end

        subgraph "frontend.yml"
            F1[Frontend Tests]
        end

        subgraph "helm-chart.yml"
            H1[Helm Lint]
            H2[Validate Templates]
            H3[Package Chart]
            H1 --> H2 --> H3
        end

        subgraph "docker-build.yml"
            D1[Build Backend Image]
            D2[Build Frontend Image]
            D3[Test Helm Deployment]
            D4[Pull Built Images]
            D5[Load to Kind]
            D6[Deploy Chart]
            D7[Run Helm Tests]

            D1 --> D3
            D2 --> D3
            D3 --> D4 --> D5 --> D6 --> D7
        end
    end

    PR --> B1
    PR --> F1
    PR --> H1
    PR --> D1
    PR --> D2

    RESULT[✅ All Checks Pass]
    B1 --> RESULT
    F1 --> RESULT
    H3 --> RESULT
    D7 --> RESULT
```

**Key Points:**
- All workflows run in parallel for fast feedback
- Images are built but NOT published on PRs
- Helm chart is validated and tested but NOT published
- Full deployment test runs in kind cluster using built images

### Main Branch Push Flow

When code is pushed to the main branch, the same workflows run but with publishing enabled:

```mermaid
graph TB
    PUSH[Push to Main Branch]

    subgraph "Parallel Workflows"
        subgraph "backend.yaml"
            B1[Backend Tests]
        end

        subgraph "frontend.yml"
            F1[Frontend Tests]
        end

        subgraph "helm-chart.yml"
            H1[Helm Lint]
            H2[Validate Templates]
            H3[Package Chart]
            H1 --> H2 --> H3
        end

        subgraph "docker-build.yml"
            D1[Build Backend Image]
            D2[Build Frontend Image]
            D3[Test Helm Deployment]
            D4[Pull Built Images]
            D5[Load to Kind]
            D6[Deploy Chart]
            D7[Run Helm Tests]
            D8[Publish Backend Image]
            D9[Publish Frontend Image]
            D10[Publish Helm Chart]

            D1 --> D3
            D2 --> D3
            D3 --> D4 --> D5 --> D6 --> D7
            D1 --> D8
            D2 --> D9
            D7 --> D10
        end
    end

    PUSH --> B1
    PUSH --> F1
    PUSH --> H1
    PUSH --> D1
    PUSH --> D2

    PUBLISH[📦 Published to GHCR]
    D8 --> PUBLISH
    D9 --> PUBLISH
    D10 --> PUBLISH

    TAGS[Tags: main, sha-abc123]
    PUBLISH --> TAGS
```

**Key Points:**
- Images published to GHCR with `main` and `sha-<commit>` tags
- Helm chart published to GHCR with same tags
- Publishing only happens AFTER successful Helm deployment test
- No `latest` tag on main branch pushes (only on releases)

### Release Tag Flow

When a release tag (e.g., `v1.2.3`) is created:

```mermaid
graph TB
    TAG[Create Release Tag v1.2.3]

    subgraph "release.yml"
        R1[Create GitHub Release]
        R2[Build Backend Image]
        R3[Build Frontend Image]
        R4[Publish Backend]
        R5[Publish Frontend]
        R6[Update Chart Version]
        R7[Package Chart]
        R8[Upload to Release]
        R9[Push to GHCR]
        R10[Deploy Test]

        TAG --> R1
        R1 --> R2
        R1 --> R3
        R2 --> R4
        R3 --> R5
        R1 --> R6
        R6 --> R7
        R7 --> R8
        R7 --> R9
        R4 --> R10
        R5 --> R10
        R9 --> R10
    end

    PUBLISHED[📦 Published to GHCR]
    R4 --> PUBLISHED
    R5 --> PUBLISHED
    R9 --> PUBLISHED

    TAGS[Image Tags: v1.2.3, v1.2, v1, latest<br/>Chart Tags: v1.2.3, v1.2, v1, latest]
    PUBLISHED --> TAGS
```

**Key Points:**
- Creates GitHub Release with release notes
- Builds and publishes images with semantic version tags
- Updates chart version to match release
- Publishes chart to both GitHub Release (`.tgz`) and GHCR (OCI)
- Runs deployment verification test
- Only releases get the `latest` tag


## Publishing Strategy

### Image Tags

| Event | Backend Tags | Frontend Tags |
|-------|-------------|---------------|
| **PR** | Not published | Not published |
| **Main Push** | `main`, `sha-<commit>` | `main`, `sha-<commit>` |
| **Release v1.2.3** | `v1.2.3`, `v1.2`, `v1`, `latest` | `v1.2.3`, `v1.2`, `v1`, `latest` |

### Helm Chart Tags

| Event | Chart Tags | Location |
|-------|-----------|----------|
| **PR** | Not published | N/A |
| **Main Push** | `main`, `sha-<commit>` | GHCR OCI |
| **Release v1.2.3** | `v1.2.3`, `v1.2`, `v1`, `latest` | GHCR OCI + GitHub Release |

**Important:** The `latest` tag is ONLY applied on releases, not on main branch pushes.

## Optimization Strategies

### Build Caching

- Docker layer caching via GitHub Actions cache
- Speeds up subsequent builds significantly
- Shared across workflow runs

### Parallel Execution

- Independent workflows run in parallel
- Reduces total CI time
- Fast feedback on failures

### Image Reuse

- Images built once in `docker-build.yml`
- Same images pulled for Helm testing
- Avoids duplicate builds
- Ensures consistency

### Conditional Publishing

- Images/charts only published on main branch
- PRs build and test but don't publish
- Reduces registry clutter
- Saves bandwidth

## Secrets and Permissions

### Required Secrets

- `GITHUB_TOKEN` - Automatically provided by GitHub Actions
- `CODECOV_TOKEN` - Optional, for code coverage reporting

### Required Permissions

**docker-build.yml:**
- `contents: read` - Read repository
- `packages: write` - Publish to GHCR
- `packages: read` - Pull images for testing

**release.yml:**
- `contents: write` - Create releases
- `packages: write` - Publish to GHCR

## Monitoring and Debugging

### Viewing Workflow Runs

```bash
# View recent workflow runs
gh run list

# View specific run
gh run view <run-id>

# Watch a running workflow
gh run watch
```

### Common Issues

**Build Failures:**
- Check build logs in GitHub Actions
- Verify Dockerfile syntax
- Check for dependency issues

**Test Failures:**
- Review test output in workflow logs
- Check for flaky tests
- Verify test environment setup

**Helm Deployment Failures:**
- Check pod logs in workflow output
- Verify chart templates
- Check resource limits
- Review PostgreSQL startup

**Publishing Failures:**
- Verify GITHUB_TOKEN permissions
- Check registry authentication
- Verify tag format

### Debugging Locally

```bash
# Test backend build
make build-backend

# Test frontend build
make build-frontend

# Test Helm chart
make helm-test

# Test Helm deployment locally
make helm-install-local
```

## Best Practices

### For Contributors

1. **Run tests locally** before pushing
2. **Keep PRs focused** to reduce CI time
3. **Fix failing tests** promptly
4. **Review workflow logs** when builds fail

### For Maintainers

1. **Monitor workflow success rates**
2. **Keep dependencies updated**
3. **Review and optimize slow workflows**
4. **Maintain build cache efficiency**
5. **Document workflow changes**

## Future Enhancements

Potential improvements to consider:

1. **Chart Signing** - Add cosign signing for Helm charts
2. **Security Scanning** - Add Trivy or Snyk scanning
3. **Performance Testing** - Add load testing to CI
4. **Multi-cluster Testing** - Test on different K8s versions
5. **Automated Rollback** - Auto-rollback on deployment failures
6. **Slack Notifications** - Notify on build failures
7. **Deployment Previews** - Preview environments for PRs

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Helm Actions](https://github.com/helm/kind-action)
- [GHCR Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)

## Support

For CI/CD issues:
- Check [GitHub Actions logs](https://github.com/afrittoli/gha-runner-token-service/actions)
- Review [workflow files](.github/workflows/)
- Open an [issue](https://github.com/afrittoli/gha-runner-token-service/issues)