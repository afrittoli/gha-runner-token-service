# Dashboard Design

## Current Implementation

The dashboard is currently a **basic server-rendered HTML page** using Jinja2 templates. It provides:

- Runner statistics (total, active, offline, pending)
- Runner list with status, labels, and provisioned by
- Recent security events table
- Manual refresh button (page reload)

**Access:** `http://localhost:8000/dashboard` (no authentication required currently)

**Files:**
- `app/templates/dashboard.html` - HTML template
- `app/main.py` - Dashboard endpoint

## Known Limitations

1. **No authentication** - Dashboard is publicly accessible
2. **No real-time updates** - Manual page refresh required
3. **Read-only** - No runner management actions
4. **Shows OIDC sub, not email** - User display name issue (depends on user provisioning feature)

---

## Future: Full Dashboard Specification

The sections below describe a more complete dashboard implementation for future development.

### Requirements

**Authentication & Authorization:**
- OIDC-based authentication (reuse service's OIDC config)
- Role-based access control (Admin vs. Standard User)
- Session management with token refresh

**Admin Capabilities:**
- View all provisioned runners across all users
- Filter/search runners by user, status, labels
- Deprovision individual or bulk runners
- View and manage label policies
- Query security events and audit logs

**Standard User Capabilities:**
- View own provisioned runners only
- Read-only access to runner status
- View own audit trail

### Technology Options

**Option A: Jinja2 + HTMX (simpler)**
- Server-rendered templates
- HTMX for partial page updates
- Minimal JavaScript
- Faster to implement

**Option B: React SPA (more capable)**
- React 18 with TypeScript
- TanStack Query for server state
- shadcn/ui components
- Richer interactivity

### Page Structure

**Dashboard Home:**
- Overview statistics
- Recent activity feed
- Quick actions

**Runners List:**
- Filterable, sortable table
- Status badges with colors
- Row actions (view, refresh, delete)
- Pagination

**Runner Detail:**
- Full metadata
- Activity timeline
- Action buttons

**Admin Pages (admin only):**
- Label Policies management
- Security Events viewer
- Audit Log viewer

### Status Indicators

| Status | Color | Hex |
|--------|-------|-----|
| Active | Green | #28a745 |
| Offline | Red | #dc3545 |
| Pending | Amber | #ffc107 |
| Deleted | Gray | #6c757d |

### Implementation Priority

1. Add dashboard authentication (cookie/session based)
2. Add runner management actions (refresh, delete)
3. Add filtering and sorting
4. Add label policy management UI
5. Add security events viewer
6. Consider React migration if complexity warrants
