# Team Management Guide

## Overview

Team-based authorization allows you to organize users into teams with specific runner provisioning policies.

### Data Model

![Data Model](diagrams/data_model.svg)

The team-based authorization system uses a many-to-many relationship between Users and Teams through the UserTeamMembership table. See the [data model diagram](diagrams/data_model.svg) for complete schema details.

### Team Features

Each team can have:
- **Required labels**: Labels that must be present on all runners
- **Optional label patterns**: Regex patterns for additional allowed labels
- **Runner quotas**: Maximum number of active runners per team
- **Members**: Users with either "member" or "admin" roles

## Key Concepts

### Teams
Teams are organizational units that group users and define runner provisioning policies. Teams can be active or inactive (soft-deleted).

### Team Membership
Users can belong to multiple teams with different roles:
- **Member**: Can provision runners using team policies
- **Admin**: Can manage team settings and members (future feature)

### Label Policies
Teams enforce label policies on runner provisioning:
- **Required labels**: Always applied to runners (e.g., `["linux", "docker"]`)
- **Optional patterns**: Regex patterns for dynamic labels (e.g., `["project-.*", "env-.*"]`)
- Labels are validated server-side during JIT provisioning

### Runner Quotas
Teams can have maximum runner limits to prevent resource exhaustion. When a team reaches its quota, new provisioning requests are rejected.

## M2M (Machine-to-Machine) Authentication

With M2M authentication, CI/CD pipelines and automation tools obtain runner tokens directly using OAuth `client_credentials` grant — no human login required.

### How M2M Works

1. An Auth0 M2M application is created per team (managed outside gharts)
2. The M2M app is registered in gharts with `POST /admin/oauth-clients`
3. An Auth0 Action injects the `team` claim into the JWT for that client
4. The pipeline exchanges its `client_id`/`client_secret` for a JWT from Auth0
5. The JWT (containing `team: "<team-name>"`) is used as a Bearer token against gharts API
6. gharts validates the token, resolves the team, and provisions runners under that team

### M2M vs Individual Tokens

| Feature | M2M (team) | Individual (user) |
|---------|------------|-------------------|
| Grant type | `client_credentials` | Device/PKCE |
| Team selection | Embedded in JWT | Required per request |
| Runner scope visible | Own team only | All user runners + team runners |
| Requires team membership | No | Yes |
| Blocked by team deactivation | Yes | Yes |

### Registering an M2M Client

```bash
# Register a new Auth0 M2M client for a team
curl -X POST https://your-domain.com/admin/oauth-clients \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "auth0-client-id-from-m2m-app",
    "team_id": "TEAM_UUID",
    "description": "CI/CD pipeline for backend team"
  }'
```

### Listing M2M Clients for a Team

```bash
# List active clients for a specific team
curl "https://your-domain.com/admin/oauth-clients?team_id=TEAM_UUID&active_only=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# List all clients (including inactive)
curl "https://your-domain.com/admin/oauth-clients?active_only=false" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Admin Workflows

### Creating a Team

**Via API:**
```bash
curl -X POST https://your-domain.com/api/v1/admin/teams \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Backend Team",
    "description": "Backend services development",
    "required_labels": ["linux", "docker"],
    "optional_label_patterns": ["backend-.*", "service-.*"],
    "max_runners": 10
  }'
```

**Via Dashboard:**
1. Navigate to Admin Console → Teams
2. Click "Create Team"
3. Fill in team details:
   - Name (required)
   - Description (optional)
   - Required labels (comma-separated)
   - Optional label patterns (regex, comma-separated)
   - Max runners (optional, leave empty for unlimited)
4. Click "Create Team"

### Adding Members to a Team

**Via API:**
```bash
curl -X POST https://your-domain.com/api/v1/admin/teams/TEAM_ID/members \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user@example.com",
    "role": "member"
  }'
```

**Via Dashboard:**
1. Navigate to Admin Console → Teams
2. Click "Manage Members" for the desired team
3. Click "Add Member"
4. Enter user email/ID
5. Select role (Member or Admin)
6. Click "Add Member"

### Updating Team Policies

**Via API:**
```bash
curl -X PATCH https://your-domain.com/api/v1/admin/teams/TEAM_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "required_labels": ["linux", "docker", "kubernetes"],
    "max_runners": 15
  }'
```

**Via Dashboard:**
1. Navigate to Admin Console → Teams
2. Click on team name to edit
3. Update desired fields
4. Click "Save Changes"

### Deactivating a Team

When a team is deactivated:
- `is_active` is set to `false` — the reason, timestamp, and admin identity are recorded
- **M2M tokens** for this team are immediately rejected (403 Forbidden) — pipelines cannot provision runners
- **Individual users** who are members of this team can no longer provision runners for it
- Existing runners are **not deleted** (soft disable only)
- The team can be reactivated at any time

**Via API:**
```bash
curl -X POST https://your-domain.com/api/v1/teams/TEAM_ID/deactivate \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Team restructured — pending migration to new-team"}'
```

**Via Dashboard:**
1. Navigate to Admin Console → Teams
2. Click "Deactivate" for the desired team
3. Enter a reason (required)
4. Confirm the action

### Reactivating a Team

```bash
curl -X POST https://your-domain.com/api/v1/teams/TEAM_ID/reactivate \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Disabling a Single M2M Client (without deactivating the team)

To revoke access for one pipeline while keeping others running:

```bash
# Disable a specific OAuth client (the team stays active)
curl -X PATCH https://your-domain.com/admin/oauth-clients/CLIENT_RECORD_UUID \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

> **Note:** Disabling the OAuthClient record alone does not prevent tokens that are already issued (JWTs are stateless). To fully block a team immediately, deactivate the team itself.

### Permanently Removing an M2M Client

```bash
curl -X DELETE https://your-domain.com/admin/oauth-clients/CLIENT_RECORD_UUID \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Admin Bulk Operations

All bulk operations require a mandatory `comment` field (10–500 characters) for the audit trail.

### Bulk Disable Users

Disables multiple user accounts — useful during security incidents or offboarding.

```bash
# Disable specific users
curl -X POST https://your-domain.com/api/v1/admin/batch/disable-users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Security incident: contractor accounts suspended pending review",
    "user_ids": ["uuid1", "uuid2"],
    "exclude_admins": true
  }'

# Disable ALL non-admin users (omit user_ids)
curl -X POST https://your-domain.com/api/v1/admin/batch/disable-users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Emergency lockdown: all users disabled",
    "exclude_admins": true
  }'
```

Response includes `affected_count`, `failed_count`, and per-user details.

### Bulk Restore Users

Re-enables previously disabled user accounts.

```bash
# Restore specific users
curl -X POST https://your-domain.com/api/v1/admin/batch/restore-users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Security review complete — accounts restored",
    "user_ids": ["uuid1", "uuid2"]
  }'

# Restore ALL inactive users (omit user_ids)
curl -X POST https://your-domain.com/api/v1/admin/batch/restore-users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Post-incident full restoration"}'
```

### Bulk Delete Runners

Removes runners in bulk. Three modes:

```bash
# Delete specific runners by ID
curl -X POST https://your-domain.com/api/v1/admin/batch/delete-runners \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Stale runners from decommissioned team",
    "runner_ids": ["runner-uuid-1", "runner-uuid-2"]
  }'

# Delete all runners for a specific user/identity
curl -X POST https://your-domain.com/api/v1/admin/batch/delete-runners \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "User offboarded",
    "user_identity": "user@example.com"
  }'

# Delete ALL runners (use with extreme caution)
curl -X POST https://your-domain.com/api/v1/admin/batch/delete-runners \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Full environment reset"}'
```

> Runners are soft-deleted (`status=deleted`, `deleted_at` recorded). GitHub deletion is attempted but non-blocking.

### Bulk Team Deactivation

```bash
# Deactivate specific teams
curl -X POST https://your-domain.com/api/v1/admin/batch/deactivate-teams \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Org restructuring: deactivating contractor teams",
    "team_ids": ["uuid1", "uuid2"],
    "reason": "Org restructuring Q1-2026"
  }'

# Deactivate ALL active teams (omit team_ids)
curl -X POST https://your-domain.com/api/v1/admin/batch/deactivate-teams \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Emergency: suspending all team runner creation",
    "reason": "Security incident"
  }'
```

### Bulk Team Reactivation

```bash
# Reactivate specific teams
curl -X POST https://your-domain.com/api/v1/admin/batch/reactivate-teams \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Incident resolved: restoring team access",
    "team_ids": ["uuid1", "uuid2"]
  }'

# Reactivate ALL inactive teams (omit team_ids)
curl -X POST https://your-domain.com/api/v1/admin/batch/reactivate-teams \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Post-incident full restoration"}'
```

Both operations skip teams already in the target state and return `affected_count`, `failed_count`, and per-team details.

---

## Incident Response Playbooks

### Scenario: Prevent a team from creating any new runners

This covers both M2M pipelines and individual users who are members.

**Immediate action — deactivate the team:**
```bash
curl -X POST https://your-domain.com/api/v1/teams/TEAM_ID/deactivate \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Security incident — runner creation suspended"}'
```

Effect: All M2M tokens with `team: "<team-name>"` receive `403 Forbidden` immediately. Individual users who try to provision for this team are also blocked.

**Optional: delete existing runners for the team:**
```bash
# First find runners for this team
curl "https://your-domain.com/api/v1/runners?team_id=TEAM_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Then bulk delete them
curl -X POST https://your-domain.com/api/v1/admin/batch/delete-runners \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Security incident cleanup",
    "runner_ids": ["id1", "id2", ...]
  }'
```

### Scenario: Prevent ALL teams from creating new runners

```bash
curl -X POST https://your-domain.com/api/v1/admin/batch/deactivate-teams \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comment": "Emergency: suspending all team runner creation",
    "reason": "Security incident — all teams suspended pending review"
  }'
```

### Scenario: Revoke a specific pipeline's access without affecting the team

```bash
# 1. Find the client record for the pipeline
curl "https://your-domain.com/admin/oauth-clients?team_id=TEAM_UUID" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# 2. Disable the specific client
curl -X PATCH "https://your-domain.com/admin/oauth-clients/CLIENT_RECORD_UUID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

> JWTs already issued remain valid until they expire. To cut off access before expiry, deactivate the team instead.

### Scenario: Full lockdown (all users + all teams)

```bash
# 1. Disable all non-admin users
curl -X POST https://your-domain.com/api/v1/admin/batch/disable-users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Emergency lockdown", "exclude_admins": true}'

# 2. Deactivate all teams
curl -X POST https://your-domain.com/api/v1/admin/batch/deactivate-teams \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Emergency lockdown: all teams deactivated", "reason": "Security incident"}'

# 3. Restore after incident resolved
curl -X POST https://your-domain.com/api/v1/admin/batch/restore-users \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"comment": "Post-incident restoration"}'
```

## User Workflows

### Viewing My Teams

**Via API:**
```bash
curl https://your-domain.com/api/v1/teams/my-teams \
  -H "Authorization: Bearer $TOKEN"
```

**Via Dashboard:**
1. Navigate to Provision Runner page
2. Team dropdown shows all your active teams

### Provisioning a Runner with Team

**Via API:**
```bash
curl -X POST https://your-domain.com/api/v1/runners/jit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "runner_name_prefix": "backend-runner",
    "labels": ["backend-api", "service-auth"],
    "team_id": "TEAM_ID"
  }'
```

**Via Dashboard:**
1. Navigate to Provision Runner
2. Select team from dropdown (required if you belong to any teams)
3. Enter runner name prefix (optional)
4. Enter custom labels (comma-separated)
5. Click "Provision JIT Runner"

**Label Validation:**
- System labels (`self-hosted`, `linux`, `x64`) are added automatically
- Required team labels are enforced
- Custom labels must match optional patterns
- Validation errors are returned immediately

### Understanding Label Policies

When provisioning with a team:

1. **Required labels** are automatically included
2. **Custom labels** must match optional patterns
3. **System labels** are always added

**Example:**
- Team policy: `required_labels=["docker"]`, `optional_label_patterns=["app-.*"]`
- User provides: `labels=["app-backend", "gpu"]`
- Result: ✅ `app-backend` matches pattern, ❌ `gpu` rejected
- Final labels: `["self-hosted", "linux", "x64", "docker", "app-backend"]`

## Migration from User-Based Policies

### Backward Compatibility

The system maintains backward compatibility:
- **User-based label policies** continue to work
- **Team-based policies** are opt-in
- Users without teams use user-based policies
- Users with teams must select a team when provisioning

### Migration Steps

1. **Create teams** matching your organizational structure
2. **Add members** to appropriate teams
3. **Test provisioning** with team selection
4. **Gradually migrate** users from individual policies to teams
5. **Deprecate** user-based policies once migration is complete

### Coexistence Period

During migration:
- Users with NO teams: Use user-based label policies
- Users with teams: MUST select a team (team dropdown is required)
- Admins can manage both user and team policies

## Best Practices

### Team Organization

1. **Align with org structure**: Create teams matching your departments/projects
2. **Clear naming**: Use descriptive team names (e.g., "Backend-Services", "ML-Research")
3. **Documented policies**: Add descriptions explaining label requirements

### Label Policy Design

1. **Required labels**: Use for mandatory infrastructure labels (e.g., `["linux", "docker"]`)
2. **Optional patterns**: Use for project-specific labels (e.g., `["project-.*", "env-.*"]`)
3. **Avoid over-restriction**: Allow flexibility with patterns rather than exhaustive lists

### Quota Management

1. **Set realistic limits**: Based on team size and workload
2. **Monitor usage**: Check runner counts regularly
3. **Adjust as needed**: Increase quotas for growing teams

### Member Management

1. **Regular audits**: Review team memberships quarterly
2. **Remove inactive users**: Clean up when people leave
3. **Role assignment**: Use "admin" role sparingly (future feature)

## Troubleshooting

### "Team quota exceeded" Error

**Cause:** Team has reached maximum runner limit

**Solution:**
1. Check current runner count: `GET /api/v1/runners?team_id=TEAM_ID`
2. Remove idle/offline runners
3. Request quota increase from admin

### "Label not permitted by team policy" Error

**Cause:** Custom label doesn't match team's optional patterns

**Solution:**
1. Check team policy: `GET /api/v1/teams/my-teams`
2. Use labels matching the patterns
3. Request policy update from admin if needed

### "User not a member of team" Error

**Cause:** Trying to provision with a team you don't belong to

**Solution:**
1. Check your teams: `GET /api/v1/teams/my-teams`
2. Select a team you're a member of
3. Request team membership from admin

### Team Dropdown Not Showing

**Cause:** You don't belong to any active teams

**Solution:**
- Provision without team selection (uses user-based policies)
- Request team membership from admin

## API Reference

See [api_contract.md](api_contract.md) for complete API documentation.

### Quick Reference

**Team management (admin only unless noted):**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/teams` | GET | Any | List teams (admins see all, users see own) |
| `/api/v1/teams` | POST | Admin | Create team |
| `/api/v1/teams/{id}` | PATCH | Admin | Update team config |
| `/api/v1/teams/{id}/deactivate` | POST | Admin | Deactivate team |
| `/api/v1/teams/{id}/reactivate` | POST | Admin | Reactivate team |
| `/api/v1/teams/{id}/members` | GET | Any | List members |
| `/api/v1/teams/{id}/members` | POST | Admin | Add member |
| `/api/v1/teams/{id}/members/{user_id}` | DELETE | Admin | Remove member |
| `/api/v1/teams/users/{user_id}/teams` | GET | Any | Get user's teams |

**M2M client management (admin only):**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/oauth-clients` | POST | Register M2M client for a team |
| `/admin/oauth-clients` | GET | List M2M clients |
| `/admin/oauth-clients/{id}` | GET | Get client details |
| `/admin/oauth-clients/{id}` | PATCH | Update client (description, active status) |
| `/admin/oauth-clients/{id}` | DELETE | Remove client registration |

**Bulk admin operations (admin only):**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/batch/disable-users` | POST | Bulk disable users |
| `/api/v1/admin/batch/restore-users` | POST | Bulk restore users |
| `/api/v1/admin/batch/delete-runners` | POST | Bulk delete runners |
| `/api/v1/admin/batch/deactivate-teams` | POST | Bulk deactivate teams |
| `/api/v1/admin/batch/reactivate-teams` | POST | Bulk reactivate teams |

**User-facing:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/runners/jit` | POST | Provision JIT runner (with team) |
| `/api/v1/runners/registration-token` | POST | Get registration token (with team) |

## Security Considerations

### Access Control

- **Team management**: Admin-only operations
- **Member operations**: Admins can add/remove any user
- **Provisioning**: Members can only provision for their own teams
- **Audit trail**: All operations are logged with team context

### Label Enforcement

- **Server-side validation**: Labels validated during provisioning
- **No client bypass**: Frontend restrictions backed by API validation
- **Drift detection**: JIT runners monitored for label changes

### Quota Enforcement

- **Hard limits**: Provisioning blocked when quota reached
- **Per-team isolation**: One team's quota doesn't affect others
- **Admin override**: Admins can adjust quotas as needed

## Future Enhancements

Planned features for team management:

1. **Team admin role**: Allow team admins to manage their own team
2. **Nested teams**: Support team hierarchies
3. **Resource pools**: Assign specific runner pools to teams
4. **Cost tracking**: Track runner usage costs per team
5. **Self-service**: Allow users to request team membership

---

**Last Updated:** 2026-03-09
**Version:** 1.1.0