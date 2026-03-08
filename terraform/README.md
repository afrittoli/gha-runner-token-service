# Terraform — gharts Auth0 Infrastructure

This directory contains a Terraform module that provisions all Auth0 resources
required by gharts, plus an example environment showing how to call it.

```
terraform/
├── modules/
│   └── auth0/           # Reusable module — Auth0 API, apps, actions, flows
└── environments/
    └── example/         # Quick-start environment for a single tenant
```

## What gets created

| Resource | Count | Purpose |
|----------|-------|---------|
| `auth0_resource_server` | 1 | API definition (audience / identifier) |
| `auth0_client` (SPA) | 1 | React frontend — authorization_code + PKCE |
| `auth0_client` (Native CLI) | 1 | Device code flow for interactive demos |
| `auth0_client` (M2M) | N per team | `client_credentials` grant for CI/CD pipelines |
| `auth0_client_grant` | N per team | Authorises each M2M app to call the API |
| `auth0_action` (post-token) | 1 | Injects `team` claim into M2M tokens |
| `auth0_action` (post-login) | 0 or 1 | Injects `teams` claim into user tokens (optional) |
| `auth0_trigger_actions` | 1–2 | Wires actions into the correct trigger pipeline |

## Quick start

```bash
cd environments/example
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with your Auth0 domain and management credentials
terraform init
terraform plan
terraform apply
```

See [environments/example/README.md](environments/example/README.md) for full
setup instructions and [modules/auth0/README.md](modules/auth0/README.md) for
the complete module reference.

## Design decisions

### One M2M application per team

Each team gets its own Auth0 M2M application. This provides:

- **Blast-radius isolation** — revoking one team's credentials does not affect others
- **Independent rotation** — secrets can be rotated per team without coordination
- **Clear audit trail** — Auth0 logs show which team's app made each token request
- **Simple claim injection** — the Action reads `event.client.metadata.team` directly

The alternative (one shared M2M app with a team query parameter) would require
custom token-exchange logic and lose the per-team isolation benefits.

### Auth0 Actions instead of Rules

Auth0 Rules are deprecated. Actions are the current recommended approach for
customising tokens and are supported by the Terraform provider.
