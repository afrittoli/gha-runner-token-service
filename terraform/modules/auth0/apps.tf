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
# M2M applications have been removed as part of Proposal B-1.
#
# CI/CD pipelines now authenticate using GHARTS-native opaque API keys
# issued via POST /api/v1/admin/oauth-clients.  No Auth0 M2M applications,
# client secrets, or credentials-exchange tokens are required.
#
# To destroy existing Auth0 M2M apps, run:
#   terraform state rm 'module.auth0.auth0_client.m2m_team'
#   terraform state rm 'module.auth0.auth0_client_credentials.m2m_team'
#   terraform state rm 'module.auth0.auth0_client_grant.m2m_team'
# then apply; Auth0 will not automatically delete the apps so they should
# also be removed manually from the Auth0 dashboard or via the management API.
# ---------------------------------------------------------------------------
