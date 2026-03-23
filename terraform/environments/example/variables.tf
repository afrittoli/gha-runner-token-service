variable "auth0_domain" {
  description = "Auth0 tenant domain (without https://)"
  type        = string
}

variable "auth0_mgmt_client_id" {
  description = "Management API application client ID"
  type        = string
  sensitive   = true
}

variable "auth0_mgmt_client_secret" {
  description = "Management API application client secret"
  type        = string
  sensitive   = true
}

variable "spa_callback_urls" {
  description = "Allowed callback URLs for the SPA application"
  type        = list(string)
}

variable "spa_logout_urls" {
  description = "Allowed logout URLs for the SPA application"
  type        = list(string)
}

variable "spa_web_origins" {
  description = "Allowed web origins for the SPA application"
  type        = list(string)
}

# ---------------------------------------------------------------------------
# Removed variables (Proposal B-1)
# ---------------------------------------------------------------------------
# variable "teams" -- Auth0 M2M apps are no longer provisioned via Terraform.
#                     Teams and their API keys are managed via the GHARTS admin API:
#                     POST /api/v1/admin/oauth-clients
