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
# M2M applications — one per team (client_credentials grant)
# ---------------------------------------------------------------------------
resource "auth0_client" "m2m_team" {
  for_each = local.teams_set

  name     = "gharts-${each.key}"
  app_type = "non_interactive"

  grant_types = ["client_credentials"]

  oidc_conformant = true

  jwt_configuration {
    alg = "RS256"
  }
}

# Read back the auto-generated client secret for each M2M app
resource "auth0_client_credentials" "m2m_team" {
  for_each = local.teams_set

  client_id             = auth0_client.m2m_team[each.key].client_id
  authentication_method = "client_secret_post"
}

# Grant each M2M app access to the API
resource "auth0_client_grant" "m2m_team" {
  for_each = local.teams_set

  client_id = auth0_client.m2m_team[each.key].client_id
  audience  = auth0_resource_server.api.identifier
  scopes    = []
}
