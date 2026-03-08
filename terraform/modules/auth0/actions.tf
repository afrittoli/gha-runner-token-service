# ---------------------------------------------------------------------------
# Action: Add Team Claim
# Trigger: credentials-exchange (Machine-to-Machine / client_credentials flow)
#
# Copies the `team` key from the M2M app's metadata into the access token.
# This allows the gharts backend to resolve team context from the JWT alone,
# without a database user lookup.
# ---------------------------------------------------------------------------
resource "auth0_action" "add_team_claim" {
  name    = "Add Team Claim"
  runtime = "node18"
  deploy  = true

  supported_triggers {
    id      = "credentials-exchange"
    version = "v2"
  }

  code = <<-JS
    /**
     * Add Team Claim Action (credentials-exchange / Machine-to-Machine trigger)
     *
     * Reads event.client.metadata.team and injects it as a custom claim
     * into the access token so the backend can resolve team context without
     * a database user lookup.
     */
    exports.onExecuteCredentialsExchange = async (event, api) => {
      const team = event.client && event.client.metadata && event.client.metadata.team;
      if (team) {
        api.accessToken.setCustomClaim("team", team);
      }
    };
  JS
}

# ---------------------------------------------------------------------------
# Action: Add User Teams  (optional — only created when embed_user_teams=true)
# Trigger: post-login
#
# Copies the user's `teams` array from app_metadata into the id_token and
# access_token so the SPA can show team-scoped views without an extra API call.
# ---------------------------------------------------------------------------
resource "auth0_action" "add_user_teams" {
  count = var.embed_user_teams ? 1 : 0

  name    = "Add User Teams"
  runtime = "node18"
  deploy  = true

  supported_triggers {
    id      = "post-login"
    version = "v3"
  }

  code = <<-JS
    /**
     * Add User Teams Action (post-login trigger)
     *
     * Embeds the user's team memberships (stored in app_metadata.teams) into
     * both the id_token and access_token as a "teams" claim.
     * The value is an array of team name strings.
     */
    exports.onExecutePostLogin = async (event, api) => {
      const teams = event.user.app_metadata && event.user.app_metadata.teams;
      if (Array.isArray(teams) && teams.length > 0) {
        api.idToken.setCustomClaim("teams", teams);
        api.accessToken.setCustomClaim("teams", teams);
      }
    };
  JS
}
