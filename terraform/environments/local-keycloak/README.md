# Local Keycloak Test Environment

This Terraform configuration is used to validate the Keycloak provider setup and test basic resource creation against a local Keycloak instance.

## Prerequisites

1. Start local Keycloak using the dev script:
   ```bash
   ./scripts/dev-keycloak.sh
   ```

2. Ensure Keycloak is running and accessible at `http://localhost:8080`

## Usage

```bash
# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Plan changes
terraform plan

# Apply changes (creates test realm and client)
terraform apply

# View outputs
terraform output

# Destroy resources when done
terraform destroy
```

## What This Tests

- Keycloak provider connectivity
- Realm creation
- OpenID Connect client creation with service account enabled
- Client credentials grant configuration

## Default Configuration

- **Keycloak URL**: `http://localhost:8080`
- **Admin Username**: `admin`
- **Admin Password**: `admin`
- **Test Realm**: `gharts-test`
- **Test Client**: `gharts-test-client`

## Customization

Override defaults using variables:

```bash
terraform plan -var="keycloak_url=http://localhost:9090"
```

Or create a `terraform.tfvars` file:

```hcl
keycloak_url = "http://localhost:9090"
keycloak_admin_username = "myadmin"
keycloak_admin_password = "mypassword"
```

## Notes

- This environment uses `ssl_required = "none"` which is only suitable for local development
- The test client uses `CONFIDENTIAL` access type with service accounts enabled
- Standard flow and direct access grants are disabled (M2M only)
