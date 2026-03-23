variable "auth0_domain" {
  description = "Auth0 tenant domain (without https://), e.g. your-tenant.auth0.com"
  type        = string
}

variable "auth0_client_id" {
  description = "Client ID of the Auth0 Management API application"
  type        = string
  sensitive   = true
}

variable "auth0_client_secret" {
  description = "Client secret of the Auth0 Management API application"
  type        = string
  sensitive   = true
}

variable "audience" {
  description = "API identifier (audience) for the resource server"
  type        = string
  default     = "gharts"
}

variable "spa_urls" {
  description = "Allowed URLs for the SPA application"
  type = object({
    callback    = list(string)
    logout      = list(string)
    web_origins = list(string)
  })
}

variable "embed_user_teams" {
  description = "When true, create the 'Add User Teams' post-login Action that embeds team memberships into user tokens"
  type        = bool
  default     = false
}

# ---------------------------------------------------------------------------
# Removed variables (Proposal B-1)
# ---------------------------------------------------------------------------
# variable "teams"             -- M2M apps are no longer provisioned via Terraform.
#                                 Teams are registered in GHARTS via the admin API.
# variable "m2m_token_lifetime" -- Auth0 no longer issues M2M tokens.
