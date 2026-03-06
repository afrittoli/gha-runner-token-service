terraform {
  required_version = ">= 1.7"

  required_providers {
    auth0 = {
      source  = "registry.terraform.io/auth0/auth0"
      version = "~> 1.0"
    }
  }
}

provider "auth0" {
  domain        = var.auth0_domain
  client_id     = var.auth0_client_id
  client_secret = var.auth0_client_secret
}

locals {
  # Normalise team names to lower-case and replace spaces with hyphens
  # so they are safe to embed in resource names.
  teams_set = toset([for t in var.teams : lower(replace(t, " ", "-"))])
}
