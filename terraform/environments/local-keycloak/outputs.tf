output "realm_id" {
  description = "ID of the test realm"
  value       = keycloak_realm.test.id
}

output "client_id" {
  description = "Client ID of the test client"
  value       = keycloak_openid_client.test.client_id
}

output "client_secret" {
  description = "Client secret of the test client"
  value       = keycloak_openid_client.test.client_secret
  sensitive   = true
}
