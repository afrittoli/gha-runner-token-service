# API Contract: Dashboard & Backend Separation

## Overview

This document defines the API contract between frontend dashboard(s) and the backend service. It ensures clear separation of concerns and allows independent development of dashboard features and backend functionality.

## Principles

1. **Backward Compatibility**: Existing Jinja2 dashboard (`/dashboard`) continues to work with existing endpoints
2. **Decoupling**: New React dashboard (`/app`) uses explicitly defined, documented endpoints
3. **Extension**: New dashboard features extend the API without modifying existing endpoints
4. **Versioning**: All dashboard endpoints are under `/api/v1/` to allow future versioning

## Existing Dashboard Endpoints

**Jinja2 Dashboard** uses these endpoints read-only (no modifications):

### Runners
- `GET /api/v1/runners` - List runners (basic query params only)
  - Used by: Jinja2 dashboard for rendering runner list
  - No breaking changes allowed

### Health & Status
- `GET /health` - Service health status
  - Used by: Jinja2 dashboard for status indicator
  - No breaking changes allowed

## New React Dashboard Endpoints

**React Dashboard** (`/app`) uses these endpoints and extensions:

### Authentication
- `GET /api/v1/auth/me` - Get current user info and roles (NEW)
  - Returns: `{ user_id, email, roles: ["admin|user"], oidc_sub }`
  - Used by: React dashboard for auth state

### Dashboard Statistics
- `GET /api/v1/dashboard/stats` - Dashboard statistics (NEW)
  - Returns: `{ total_runners, active, offline, pending, recent_events: [] }`
  - Used by: React dashboard home page

### Enhanced Runners
- `GET /api/v1/runners` - Enhanced with new query parameters (EXTENDED)
  - New params: `filters`, `sort`, `pagination`
  - Backward compatible: existing params still work
  - Used by: React dashboard runners list with advanced filtering
  - Note: Jinja2 dashboard ignores new params, works with defaults

- `GET /api/v1/runners/{id}` - Enhanced runner details (EXTENDED)
  - New fields: full audit trail, activity timeline, status history
  - Used by: React dashboard detail view
  - Jinja2 dashboard may not display new fields, but endpoint is compatible

- `POST /api/v1/runners` - Create runner (unchanged)
  - Used by: React dashboard provision modal
  - Jinja2 dashboard doesn't call this (read-only)

- `POST /api/v1/runners/{id}/deprovision` - Remove runner (unchanged)
  - Used by: React dashboard detail view
  - Jinja2 dashboard doesn't call this (read-only)

### Admin (new endpoints, gated by RBAC)
- `GET /api/v1/admin/label-policies` - Label policies list (NEW, admin only)
  - Returns: `{ policies: [{ user_identity, allowed_labels: [], label_patterns: [], max_runners, description, ... }], total }`
  - `label_patterns`: Optional array of regex patterns for dynamic label matching
  - Used by: React dashboard admin console
- `POST /api/v1/admin/label-policies` - Create/update label policy (NEW, admin only)
  - Body: `{ user_identity, allowed_labels: [], label_patterns?: [], max_runners?, description? }`
  - `label_patterns`: Optional regex patterns (e.g., "team-.*", "project-[a-z]+")
- `DELETE /api/v1/admin/label-policies/{user_identity}` - Delete policy (NEW, admin only)
- `GET /api/v1/admin/security-events` - Security events (NEW, admin only)
- `GET /api/v1/audit-logs` - Audit logs (NEW, admin only, with user filtering)

## Integration Points

### Database
- **Shared**: Runners, Audit Logs, Security Events, Label Policies tables
- **No breaking migrations**: Only additive schema changes
- **Backward compat**: Old code can ignore new fields

### Authentication
- **OIDC**: Both dashboards validate via OIDC
- **Tokens**: Same JWT tokens work for both dashboards
- **RBAC**: Same admin role checks apply to both

### Webhooks & Sync
- **Unchanged**: No dashboard uses these directly
- **Shared**: Both dashboards may display data updated by webhooks/sync

## Testing Strategy

1. **Existing Dashboard Tests**: Ensure Jinja2 dashboard continues to work
   - Test `/dashboard` renders correctly
   - Test critical endpoints return expected data
   - No regression tests needed (existing code doesn't change)

2. **API Compatibility Tests**: Ensure new params don't break existing dashboard
   - Test new query params are optional and ignored
   - Test new response fields don't cause errors
   - Test CORS headers work for both dashboards

3. **New Dashboard Tests**: Covered in DASHBOARD_TODO.md
   - Full test coverage for React components
   - E2E tests for new dashboard workflows

## Migration Path

**Phase 1-3** (Parallel):
- Jinja2 dashboard at `/dashboard` (no auth, read-only)
- React dashboard at `/app` (OIDC auth required, read+write)
- Both use same `/api/v1/` endpoints
- New endpoints only used by React dashboard

**Post-Phase 3** (After stabilization):
- Route `/dashboard` → React dashboard or remove Jinja2
- Keep `/api/v1/` unchanged for compatibility

## No-Go Areas (Breaking Changes)

Do NOT:
- Remove or rename existing fields in responses
- Change HTTP methods (e.g., GET → POST)
- Remove query parameters (only add optional ones)
- Break OIDC token validation
- Modify webhook processing
- Change database schema without migration scripts

Do:
- Add optional query parameters (default ignored)
- Add new response fields (old dashboards ignore them)
- Add new endpoints (existing dashboards unaffected)
- Update logging and error handling
- Improve performance (if backward compatible)

## Questions?

If new dashboard needs a backend change:
1. Check if it can use existing endpoints
2. If not, propose new endpoint following this contract
3. Ensure Jinja2 dashboard continues to work
4. Document the change here
5. Add tests verifying backward compatibility
