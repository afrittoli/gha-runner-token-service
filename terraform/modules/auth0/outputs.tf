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

# ---------------------------------------------------------------------------
# Removed outputs (Proposal B-1)
# ---------------------------------------------------------------------------
# output "m2m_client_ids"     -- Auth0 M2M apps no longer exist.
# output "m2m_client_secrets" -- Auth0 M2M apps no longer exist.
#                                 API keys are issued via POST /api/v1/admin/oauth-clients.
