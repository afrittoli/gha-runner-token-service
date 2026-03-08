# Auth0 Terraform Module

Provisions all Auth0 resources required by gharts:

- **Resource server** (API identifier / audience)
- **SPA application** – React frontend (authorization_code + PKCE)
- **Native CLI application** – device_code flow for interactive demos
- **M2M applications** – one per team, `client_credentials` grant
- **Auth0 Actions** – "Add Team Claim" (M2M flow) and optionally "Add User Teams" (login flow)
- **Flow bindings** – wires Actions into the correct Auth0 trigger pipelines

## Requirements

| Tool      | Version  |
|-----------|----------|
| Terraform | >= 1.7   |
| auth0/auth0 provider | ~> 1.0 |

The Auth0 Management API application used by Terraform must have the following scopes:

```
create:clients  read:clients  update:clients  delete:clients
create:resource_servers  read:resource_servers  update:resource_servers
create:client_grants  delete:client_grants
create:actions  read:actions  update:actions  delete:actions
create:trigger_bindings  update:trigger_bindings  read:trigger_bindings
```

## Usage

```hcl
module "auth0" {
  source = "../../modules/auth0"

  auth0_domain        = "your-tenant.auth0.com"
  auth0_client_id     = var.auth0_mgmt_client_id
  auth0_client_secret = var.auth0_mgmt_client_secret

  audience = "runner-token-service"

  teams = ["platform-team", "infra", "security"]

  spa_urls = {
    callback    = ["https://gharts.example.com/app/callback"]
    logout      = ["https://gharts.example.com/app"]
    web_origins = ["https://gharts.example.com"]
  }

  m2m_token_lifetime = 3600          # 1 hour (default)
  embed_user_teams   = false         # set true to add teams claim to user tokens
}
```

## Input Variables

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `auth0_domain` | `string` | — | Auth0 tenant domain (no `https://`) |
| `auth0_client_id` | `string` | — | Management API application client ID |
| `auth0_client_secret` | `string` | — | Management API application client secret |
| `audience` | `string` | `"runner-token-service"` | API resource server identifier |
| `teams` | `list(string)` | — | Team names; one M2M app per team |
| `spa_urls` | `object` | — | SPA callback / logout / web_origins lists |
| `m2m_token_lifetime` | `number` | `3600` | M2M access token lifetime in seconds |
| `embed_user_teams` | `bool` | `false` | Create "Add User Teams" post-login Action |

## Outputs

| Name | Description |
|------|-------------|
| `auth0_domain` | Auth0 tenant domain |
| `api_identifier` | Resource server identifier (audience) |
| `spa_client_id` | SPA application client ID |
| `native_cli_client_id` | Native CLI application client ID |
| `m2m_client_ids` | `map(string)` – team → M2M client ID |
| `m2m_client_secrets` | `map(string)` – team → M2M client secret **(sensitive)** |

> **Security note**: `m2m_client_secrets` is marked sensitive in Terraform state.
> Store state in an encrypted backend (e.g. S3 + SSE, Terraform Cloud) and
> retrieve secrets via `terraform output -json m2m_client_secrets` only in a
> secure context.

## Post-apply steps

After `terraform apply`, register each M2M client with gharts so the backend
can resolve tokens to teams:

```bash
# Retrieve secrets
CLIENT_IDS=$(terraform output -json m2m_client_ids)
CLIENT_SECRETS=$(terraform output -json m2m_client_secrets)

# Register each team's M2M app via the admin API
for TEAM in platform-team infra security; do
  CLIENT_ID=$(echo "$CLIENT_IDS" | jq -r ".\"$TEAM\"")
  curl -s -X POST https://gharts.example.com/api/v1/admin/oauth-clients \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"client_id\": \"$CLIENT_ID\", \"team_id\": \"<team-db-id>\", \"description\": \"M2M app for $TEAM\"}"
done
```

## Auth0 Actions

### Add Team Claim (post-token)

Runs on every `client_credentials` token request. Reads `event.client.metadata.team`
(set on the M2M application) and injects it as a `team` claim in the access token.
The gharts backend reads this claim to resolve team context without a DB user lookup.

### Add User Teams (post-login, optional)

When `embed_user_teams = true`, runs on every login. Reads
`event.user.app_metadata.teams` and embeds the array as a `teams` claim in both
the id_token and access_token. Useful if you want the SPA to display team
information without fetching `/auth/me`.
