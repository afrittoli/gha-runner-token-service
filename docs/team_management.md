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

**Via API:**
```bash
curl -X POST https://your-domain.com/api/v1/admin/teams/TEAM_ID/deactivate \
  -H "Authorization: Bearer $TOKEN"
```

**Via Dashboard:**
1. Navigate to Admin Console → Teams
2. Click "Deactivate" for the desired team
3. Confirm the action

**Note:** Deactivating a team:
- Sets `is_active=false` (soft delete)
- Prevents new runner provisioning
- Does NOT delete existing runners
- Members lose access to team resources

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

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/teams` | GET | List all teams |
| `/api/v1/admin/teams` | POST | Create team |
| `/api/v1/admin/teams/{id}` | PATCH | Update team |
| `/api/v1/admin/teams/{id}/deactivate` | POST | Deactivate team |
| `/api/v1/admin/teams/{id}/members` | GET | List members |
| `/api/v1/admin/teams/{id}/members` | POST | Add member |
| `/api/v1/admin/teams/{id}/members/{user_id}` | DELETE | Remove member |
| `/api/v1/teams/my-teams` | GET | List my teams |
| `/api/v1/runners/jit` | POST | Provision with team |

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

**Last Updated:** 2026-01-29  
**Version:** 1.0.0