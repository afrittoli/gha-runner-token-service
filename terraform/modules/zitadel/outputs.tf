output "zitadel_issuer" {
  description = "Zitadel token issuer URL — set as ZITADEL_ISSUER in GHARTS config"
  value       = "https://${var.zitadel_domain}"
}

output "zitadel_jwks_url" {
  description = "Zitadel JWKS URL — set as ZITADEL_JWKS_URL in GHARTS config"
  value       = "https://${var.zitadel_domain}/oauth/v2/keys"
}

output "m2m_user_ids" {
  description = "Map of team name → Zitadel machine-user ID (register as OAuthClient.client_id in GHARTS)"
  value       = { for team, user in zitadel_machine_user.m2m_team : team => user.id }
}

output "m2m_client_secrets" {
  description = "Map of team name → machine-user client secret (sensitive)"
  value       = { for team, secret in zitadel_machine_user_secret.m2m_team : team => secret.client_secret }
  sensitive   = true
}
