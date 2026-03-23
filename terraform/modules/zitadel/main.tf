terraform {
  required_version = ">= 1.7"

  required_providers {
    zitadel = {
      source  = "registry.terraform.io/zitadel/zitadel"
      version = "~> 2.0"
    }
  }
}

provider "zitadel" {
  domain           = var.zitadel_domain
  insecure         = false
  port             = "443"
  jwt_profile_file = var.zitadel_jwt_profile_file
}

locals {
  # Normalise team names to lower-case and replace spaces with hyphens
  teams_set = toset([for t in var.teams : lower(replace(t, " ", "-"))])
}

# ---------------------------------------------------------------------------
# One Zitadel machine-user (service account) per team.
# Machine-users support the client_credentials grant natively.
# ---------------------------------------------------------------------------
resource "zitadel_machine_user" "m2m_team" {
  for_each = local.teams_set

  org_id      = var.zitadel_org_id
  user_name   = "gharts-${each.key}"
  name        = "gharts ${each.key} M2M"
  description = "GHARTS M2M service account for team '${each.key}'"

  access_token_type = "JWT"
}

# ---------------------------------------------------------------------------
# Generate a client secret for each machine-user.
# The secret is used by CI/CD pipelines in the standard client_credentials
# token request.  Secrets can be rotated independently of Auth0 by the
# GHARTS team via the Zitadel management API or Terraform.
# ---------------------------------------------------------------------------
resource "zitadel_machine_user_secret" "m2m_team" {
  for_each = local.teams_set

  org_id  = var.zitadel_org_id
  user_id = zitadel_machine_user.m2m_team[each.key].id
}
