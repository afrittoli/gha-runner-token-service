# Keycloak Setup Guide

This guide explains how to deploy and configure Keycloak as the M2M OIDC provider for GHARTS (GitHub Actions Runner Token Service).

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Deployment Steps](#deployment-steps)
- [Verification](#verification)
- [Next Steps](#next-steps)

## Overview

Keycloak serves as the M2M (machine-to-machine) OIDC provider for GHARTS, enabling team-level authentication for runner provisioning automation. This setup allows CI/CD pipelines to obtain tokens using the OAuth2 client_credentials grant without requiring user interaction.

**Key Points:**
- Keycloak handles **M2M authentication only** (runner provisioning automation)
- Auth0 continues to handle **user authentication** (dashboard, CLI)
- Both providers operate simultaneously (dual-provider mode)
- Each team gets its own Keycloak client with isolated credentials

## Prerequisites

Before starting, ensure you have:

- **EKS Cluster**: Running Kubernetes cluster with kubectl access
- **cert-manager**: Installed and configured for TLS certificate management
- **nginx-ingress**: Installed and configured for ingress routing
- **Terraform**: Version 1.2 or higher
- **Helm**: Version 3.x
- **kubectl**: Configured to access your cluster
- **Access to ci-infra repository**: For Terraform configurations
- **Admin access to GHARTS**: To register M2M clients

## Architecture

The architecture shows Keycloak deployed in the same EKS cluster as GHARTS, with its own RDS database for high availability.

## Deployment Steps

### Step 1: Deploy Keycloak Infrastructure

Deploy the RDS instance for Keycloak's database.

**Location**: ci-infra/arc/aws/391835788720/us-east-1/01_infra/

1. Navigate to the infrastructure directory
2. Review the Terraform configuration for Keycloak RDS
3. Initialize and apply Terraform
4. Note the outputs (RDS endpoint, database name, username)
5. Retrieve the database password from AWS Secrets Manager

### Step 2: Deploy Keycloak Helm Chart

Deploy Keycloak to the Kubernetes cluster using Helm.

**Location**: ci-infra/arc/aws/391835788720/us-east-1/02_helm/

Expected: 2 Keycloak pods running (HA configuration)

### Step 3: Configure Keycloak Realm

Configure the gharts realm with required settings.

**Location**: ci-infra/arc/aws/391835788720/us-east-1/03_keycloak/

### Step 4: Configure GHARTS Module

Use the GHARTS Terraform module to create team-specific Keycloak clients.

### Step 5: Register M2M Client in GHARTS

Register the Keycloak client in GHARTS to enable authentication.

### Step 6: Test M2M Flow

Verify the complete M2M authentication and runner provisioning flow.

### Step 7: Enable Dual-Provider Mode

Configure GHARTS to accept tokens from both Auth0 and Keycloak.

## Verification

Verify infrastructure, Keycloak configuration, GHARTS integration, and end-to-end M2M flow.

## Next Steps

1. Migrate Teams
2. Update CI/CD Pipelines
3. Monitor
4. Security Review
5. Documentation

## Related Documentation

- [Auth0 to Keycloak Migration Guide](auth0_to_keycloak_migration.md)
- [Keycloak Troubleshooting Guide](keycloak_troubleshooting.md)
- [M2M Secret Rotation Runbook](runbooks/m2m_secret_rotation.md)
- [OIDC Setup Guide](oidc_setup.md)
