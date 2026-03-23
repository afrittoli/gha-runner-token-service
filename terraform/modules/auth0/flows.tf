# ---------------------------------------------------------------------------
# Flow binding: post-login → Add User Teams  (only when embed_user_teams=true)
# ---------------------------------------------------------------------------
resource "auth0_trigger_actions" "post_login" {
  count = var.embed_user_teams ? 1 : 0

  trigger = "post-login"

  actions {
    id           = auth0_action.add_user_teams[0].id
    display_name = auth0_action.add_user_teams[0].name
  }
}
