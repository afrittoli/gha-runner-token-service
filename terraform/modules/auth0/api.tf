# Auth0 Resource Server (API definition)
resource "auth0_resource_server" "api" {
  name       = "gharts API (${var.audience})"
  identifier = var.audience

  signing_alg                                     = "RS256"
  token_lifetime                                  = var.m2m_token_lifetime
  allow_offline_access                            = false
  skip_consent_for_verifiable_first_party_clients = true
}
