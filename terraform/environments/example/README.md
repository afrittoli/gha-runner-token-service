# Example Environment

Quick-start environment that calls the `modules/auth0` module with variables
suitable for a single Auth0 tenant.

## Prerequisites

- Terraform >= 1.7 ([install](https://developer.hashicorp.com/terraform/install))
- An Auth0 tenant
- A **Management API** Machine-to-Machine application in that tenant with the
  scopes listed in `../../modules/auth0/README.md`

## Setup

1. Copy the example vars file and fill in your values:

   ```bash
   cp terraform.tfvars.example terraform.tfvars
   $EDITOR terraform.tfvars
   ```

   Or export environment variables instead:

   ```bash
   export TF_VAR_auth0_domain="your-tenant.auth0.com"
   export TF_VAR_auth0_mgmt_client_id="..."
   export TF_VAR_auth0_mgmt_client_secret="..."
   ```

2. Initialise and plan:

   ```bash
   terraform init
   terraform plan
   ```

   Expected resource count: 1 API + 1 SPA + 1 CLI + N M2M apps + N grants +
   1 Add-Team-Claim action + 1 post-token flow binding (N = number of teams).

3. Apply:

   ```bash
   terraform apply
   ```

4. Retrieve client IDs for your Helm `values.yaml`:

   ```bash
   terraform output spa_client_id          # → frontend.config.oidc.clientId
   terraform output m2m_client_ids         # → per-team client IDs
   terraform output -json m2m_client_secrets  # sensitive — store securely
   ```

5. Register each M2M client with gharts (see `../../modules/auth0/README.md`
   Post-apply steps).

## State management

For real deployments, configure a remote backend in `main.tf` to keep state
encrypted and shared across your team:

```hcl
terraform {
  backend "s3" {
    bucket         = "my-terraform-state"
    key            = "gharts/auth0/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}
```
