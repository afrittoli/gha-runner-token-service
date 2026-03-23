# ---------------------------------------------------------------------------
# Flow binding: post-login → Add User Teams  (only when embed_user_teams=true)
#
# NOTE: The credentials-exchange flow binding (post_token) that attached the
# "Add Team Claim" action to M2M token issuance has been removed.  M2M tokens
# are now issued by Zitadel; Auth0 handles SPA and device-code flows only.
# ---------------------------------------------------------------------------
resource "auth0_trigger_actions" "post_login" {
  count = var.embed_user_teams ? 1 : 0

  trigger = "post-login"

  actions {
    id           = auth0_action.add_user_teams[0].id
    display_name = auth0_action.add_user_teams[0].name
  }
}
