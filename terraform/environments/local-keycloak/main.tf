terraform {
  required_version = ">= 1.7"

  required_providers {
    keycloak = {
      source  = "mrparkers/keycloak"
      version = "~> 4.0"
    }
  }
}

provider "keycloak" {
  client_id     = "admin-cli"
  username      = var.keycloak_admin_username
  password      = var.keycloak_admin_password
  url           = var.keycloak_url
  initial_login = false
}

# Create a test realm to validate provider connectivity
resource "keycloak_realm" "test" {
  realm   = "gharts-test"
  enabled = true

  display_name = "GHARTS Test Realm"

  # Security settings
  ssl_required    = "none" # Dev mode only
  password_policy = "length(8)"

  # Token settings
  access_token_lifespan = "1h"
}

# Create a test client to validate client creation
resource "keycloak_openid_client" "test" {
  realm_id  = keycloak_realm.test.id
  client_id = "gharts-test-client"
  name      = "GHARTS Test Client"
  enabled   = true

  access_type           = "CONFIDENTIAL"
  service_accounts_enabled = true
  standard_flow_enabled = false
  direct_access_grants_enabled = false

  valid_redirect_uris = [
    "http://localhost:*"
  ]
}
