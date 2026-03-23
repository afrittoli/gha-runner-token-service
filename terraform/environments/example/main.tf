terraform {
  required_version = ">= 1.7"
}

# ---------------------------------------------------------------------------
# Auth0 — SPA and device-code user flows only.
# M2M applications are no longer managed here; see module.zitadel below.
# ---------------------------------------------------------------------------
module "auth0" {
  source = "../../modules/auth0"

  auth0_domain        = var.auth0_domain
  auth0_client_id     = var.auth0_mgmt_client_id
  auth0_client_secret = var.auth0_mgmt_client_secret

  spa_urls = {
    callback    = var.spa_callback_urls
    logout      = var.spa_logout_urls
    web_origins = var.spa_web_origins
  }

  # embed_user_teams = false (default)
}

# ---------------------------------------------------------------------------
# Zitadel — M2M client_credentials token issuance (one machine-user per team)
# ---------------------------------------------------------------------------
module "zitadel" {
  source = "../../modules/zitadel"

  zitadel_domain           = var.zitadel_domain
  zitadel_org_id           = var.zitadel_org_id
  zitadel_jwt_profile_file = var.zitadel_jwt_profile_file

  teams = var.teams
}

# ---------------------------------------------------------------------------
# Convenience outputs
# ---------------------------------------------------------------------------
output "spa_client_id" {
  description = "Client ID for the React SPA — set as VITE_OIDC_CLIENT_ID"
  value       = module.auth0.spa_client_id
}

output "native_cli_client_id" {
  description = "Client ID for the Native CLI application"
  value       = module.auth0.native_cli_client_id
}

output "zitadel_issuer" {
  description = "Zitadel issuer URL — set as ZITADEL_ISSUER in GHARTS config"
  value       = module.zitadel.zitadel_issuer
}

output "zitadel_jwks_url" {
  description = "Zitadel JWKS URL — set as ZITADEL_JWKS_URL in GHARTS config"
  value       = module.zitadel.zitadel_jwks_url
}

output "m2m_user_ids" {
  description = "Map of team name → Zitadel machine-user ID (register as OAuthClient.client_id in GHARTS)"
  value       = module.zitadel.m2m_user_ids
}

output "m2m_client_secrets" {
  description = "Map of team name → Zitadel M2M client secret (sensitive)"
  value       = module.zitadel.m2m_client_secrets
  sensitive   = true
}
