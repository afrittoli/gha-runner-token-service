# ---------------------------------------------------------------------------
# Flow binding: post-login → Add User Teams  (only when embed_user_teams=true)
#
# NOTE: The former credentials-exchange flow binding ("post_token") has been
# removed as part of Proposal B-1.  M2M authentication is now handled by
# GHARTS-native opaque API keys; Auth0 is no longer involved in the M2M flow.
# ---------------------------------------------------------------------------
resource "auth0_trigger_actions" "post_login" {
  count = var.embed_user_teams ? 1 : 0

  trigger = "post-login"

  actions {
    id           = auth0_action.add_user_teams[0].id
    display_name = auth0_action.add_user_teams[0].name
  }
}
