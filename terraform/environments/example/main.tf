terraform {
  required_version = ">= 1.7"
}

module "auth0" {
  source = "../../modules/auth0"

  auth0_domain        = var.auth0_domain
  auth0_client_id     = var.auth0_mgmt_client_id
  auth0_client_secret = var.auth0_mgmt_client_secret

  teams = var.teams

  spa_urls = {
    callback    = var.spa_callback_urls
    logout      = var.spa_logout_urls
    web_origins = var.spa_web_origins
  }

  # Defaults: audience = "runner-token-service", m2m_token_lifetime = 3600
}

# ---------------------------------------------------------------------------
# Convenience outputs (forwarded from the module)
# ---------------------------------------------------------------------------
output "spa_client_id" {
  description = "Client ID for the React SPA — set as VITE_OIDC_CLIENT_ID"
  value       = module.auth0.spa_client_id
}

output "native_cli_client_id" {
  description = "Client ID for the Native CLI application"
  value       = module.auth0.native_cli_client_id
}

output "m2m_client_ids" {
  description = "Map of team name → M2M client ID"
  value       = module.auth0.m2m_client_ids
}

output "m2m_client_secrets" {
  description = "Map of team name → M2M client secret (sensitive)"
  value       = module.auth0.m2m_client_secrets
  sensitive   = true
}
