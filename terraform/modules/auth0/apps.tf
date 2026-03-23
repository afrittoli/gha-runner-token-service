# ---------------------------------------------------------------------------
# SPA application (React frontend)
# ---------------------------------------------------------------------------
resource "auth0_client" "spa" {
  name     = "gharts SPA"
  app_type = "spa"

  grant_types = ["authorization_code", "implicit", "refresh_token"]

  oidc_conformant = true

  callbacks           = var.spa_urls.callback
  allowed_logout_urls = var.spa_urls.logout
  web_origins         = var.spa_urls.web_origins
  allowed_origins     = var.spa_urls.web_origins

  jwt_configuration {
    alg = "RS256"
  }
}

# ---------------------------------------------------------------------------
# Native CLI application (device code flow for interactive demo/local usage)
# ---------------------------------------------------------------------------
resource "auth0_client" "native_cli" {
  name     = "gharts CLI"
  app_type = "native"

  grant_types = ["urn:ietf:params:oauth:grant-type:device_code", "refresh_token"]

  oidc_conformant = true

  jwt_configuration {
    alg = "RS256"
  }
}

# ---------------------------------------------------------------------------
# M2M applications have been removed from Auth0.
#
# M2M token issuance has moved to Zitadel (see terraform/modules/zitadel).
# Existing Auth0 M2M applications (auth0_client.m2m_team,
# auth0_client_credentials.m2m_team, auth0_client_grant.m2m_team) should be
# removed from state with `terraform state rm` and then deleted from the
# Auth0 tenant before the Zitadel migration is complete.
#
# Auth0 continues to serve SPA (Authorization Code + PKCE) and device-code
# flows for interactive user authentication.
# ---------------------------------------------------------------------------
