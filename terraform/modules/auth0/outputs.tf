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

