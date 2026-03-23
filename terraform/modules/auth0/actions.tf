# ---------------------------------------------------------------------------
# Action: Add User Teams  (optional — only created when embed_user_teams=true)
# Trigger: post-login
#
# Copies the user's `teams` array from app_metadata into the id_token and
# access_token so the SPA can show team-scoped views without an extra API call.
#
# NOTE: The former "Add Team Claim" credentials-exchange action has been removed
# as part of Proposal B-1.  M2M authentication is now handled by GHARTS-native
# opaque API keys; Auth0 is no longer involved in the M2M flow.
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
