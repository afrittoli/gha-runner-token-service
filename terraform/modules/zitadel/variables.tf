variable "zitadel_domain" {
  description = "Zitadel Cloud domain (without https://), e.g. your-org.zitadel.cloud"
  type        = string
}

variable "zitadel_org_id" {
  description = "Zitadel organisation ID in which M2M users are created"
  type        = string
}

variable "zitadel_jwt_profile_file" {
  description = "Path to the Zitadel service-account JWT profile JSON file (used for provider auth)"
  type        = string
  sensitive   = true
}

variable "teams" {
  description = "List of team names; one Zitadel machine-user is created per team"
  type        = list(string)
}
