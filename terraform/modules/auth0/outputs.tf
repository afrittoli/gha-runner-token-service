output "auth0_domain" {
  description = "Auth0 tenant domain"
  value       = var.auth0_domain
}

output "api_identifier" {
  description = "API resource server identifier (audience)"
  value       = auth0_resource_server.api.identifier
}

output "spa_client_id" {
  description = "Client ID of the SPA application"
  value       = auth0_client.spa.client_id
}

output "native_cli_client_id" {
  description = "Client ID of the Native CLI application"
  value       = auth0_client.native_cli.client_id
}

output "m2m_client_ids" {
  description = "Map of team name → M2M application client ID"
  value       = { for team, client in auth0_client.m2m_team : team => client.client_id }
}

output "m2m_client_secrets" {
  description = "Map of team name → M2M application client secret (sensitive)"
  value       = { for team, creds in auth0_client_credentials.m2m_team : team => creds.client_secret }
  sensitive   = true
}
