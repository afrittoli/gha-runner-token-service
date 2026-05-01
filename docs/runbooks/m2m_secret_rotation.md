# M2M Secret Rotation Runbook

This runbook provides step-by-step instructions for rotating Keycloak M2M client secrets.

## Overview

Regular secret rotation is a security best practice. This runbook ensures zero-downtime rotation.

## Prerequisites

- Terraform access to Keycloak configuration
- Admin access to GHARTS
- Access to team's CI/CD secret management

## Rotation Steps

### Step 1: Regenerate Secret in Keycloak

Use Terraform to regenerate the client secret.

### Step 2: Update CI/CD Secrets

Update the secret in the team's CI/CD environment.

### Step 3: Verify New Secret

Test authentication with the new secret before deactivating the old one.

### Step 4: Confirm Last Used

Verify the new secret is being used via GHARTS API.

## Rollback Procedure

Steps to rollback if issues occur.

## Related Documentation

- [Keycloak Setup Guide](../keycloak_setup.md)
- [Keycloak Troubleshooting Guide](../keycloak_troubleshooting.md)
