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

variable "teams" {
  description = "List of team names to provision M2M applications for"
  type        = list(string)
  default     = ["platform-team", "infra"]
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
