# Keycloak Troubleshooting Guide

This guide helps operators diagnose and resolve common Keycloak integration issues.

## Common Issues

### 401 Unauthorized from GHARTS

**Symptoms**: GHARTS rejects Keycloak tokens with 401 Unauthorized

**Possible Causes**:
- Issuer URL mismatch
- Missing audience claim
- JWKS cache issues

### 403 Forbidden - M2M Client Not Found

**Symptoms**: Token validation succeeds but GHARTS returns 403 Forbidden

**Possible Causes**:
- client_id not registered in GHARTS
- OAuthClient is inactive
- Protocol mapper misconfigured

### Keycloak Pod Not Starting

**Symptoms**: Keycloak pods in CrashLoopBackOff or Pending state

**Possible Causes**:
- Database credentials incorrect
- RDS connectivity issues
- Resource constraints

### Admin Console Unreachable

**Symptoms**: Cannot access Keycloak admin console

**Workaround**: Use kubectl port-forward

## Diagnostic Commands

Commands to diagnose issues.

## Related Documentation

- [Keycloak Setup Guide](keycloak_setup.md)
- [M2M Secret Rotation Runbook](runbooks/m2m_secret_rotation.md)
