# ---------------------------------------------------------------------------
# Flow binding: credentials-exchange → Add Team Claim
#
# Attaches the "Add Team Claim" action to the Machine-to-Machine flow so
# that every client_credentials token gets the team claim injected.
# ---------------------------------------------------------------------------
resource "auth0_trigger_actions" "post_token" {
  trigger = "credentials-exchange"

  actions {
    id           = auth0_action.add_team_claim.id
    display_name = auth0_action.add_team_claim.name
  }
}

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
