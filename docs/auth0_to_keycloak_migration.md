# Auth0 to Keycloak Migration Guide

This guide provides step-by-step instructions for migrating teams from Auth0 M2M applications to Keycloak clients.

## Overview

This migration enables teams to use Keycloak for M2M authentication while maintaining Auth0 for user authentication.

## Migration Phases

### Phase 1: Enable Dual-Provider Mode

Configure GHARTS to accept tokens from both Auth0 and Keycloak simultaneously.

### Phase 2: Per-Team Migration

Migrate teams one at a time to minimize risk.

### Phase 3: Cutover and Cleanup

Complete the migration and decommission Auth0 M2M applications.

## Rollback Procedure

Steps to rollback if issues are encountered during migration.

## Verification Commands

Commands to verify successful migration.

## Related Documentation

- [Keycloak Setup Guide](keycloak_setup.md)
- [Keycloak Troubleshooting Guide](keycloak_troubleshooting.md)
