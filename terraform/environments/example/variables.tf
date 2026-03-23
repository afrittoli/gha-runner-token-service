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
# Zitadel variables (M2M token issuance)
# ---------------------------------------------------------------------------

variable "zitadel_domain" {
  description = "Zitadel Cloud domain (without https://), e.g. your-org.zitadel.cloud"
  type        = string
}

variable "zitadel_org_id" {
  description = "Zitadel organisation ID in which M2M machine-users are created"
  type        = string
}

variable "zitadel_jwt_profile_file" {
  description = "Path to the Zitadel service-account JWT profile JSON file (provider auth)"
  type        = string
  sensitive   = true
}

variable "teams" {
  description = "List of team names; one Zitadel machine-user is created per team"
  type        = list(string)
  default     = ["platform-team", "infra"]
}
