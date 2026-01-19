# Dashboard Design

This document specifies the design for a web-based administrative dashboard for the GitHub Runner Token Service. The dashboard provides authenticated access to runner management operations with role-based access control distinguishing administrative and standard user capabilities.

## Executive Summary

The dashboard provides:
- **Admin Capabilities**: View all runners, manage policies, view security events, manage users
- **Standard User Capabilities**: View own runners only, read-only access
- **Core Features**: Real-time status updates, pagination, export, responsive design

## Requirements

### Functional Requirements

**Authentication & Authorization:**
- OIDC-based authentication (reusing service's existing OIDC configuration)
- Role-based access control (Admin vs. Standard User)
- Admin role assignment mechanism
- Session management with token refresh

**Admin Capabilities:**
- View all provisioned runners across all users
- Filter/search runners by user, status, labels
- Deprovision individual runners
- Bulk deprovision operations
- View and manage label policies
- Query security events
- View audit logs
- System health monitoring

**Standard User Capabilities:**
- View own provisioned runners only
- Read-only access to runner status
- No deprovisioning capabilities (enforce via service API)
- View own audit trail

**Core Features:**
- Real-time runner status updates
- Pagination for large datasets
- Export functionality (CSV, JSON)
- Responsive design (desktop, tablet, mobile)

### Non-Functional Requirements

**Performance:**
- Initial page load: <2 seconds
- API response rendering: <500ms
- Support 100+ concurrent users
- Efficient pagination (100 items per page)

**Security:**
- All API calls authenticated via OIDC token
- CSRF protection
- XSS prevention (input sanitization)
- Secure session storage (httpOnly cookies)
- Content Security Policy headers

**Usability:**
- Intuitive navigation
- Accessible (WCAG 2.1 AA compliance)
- Confirmation dialogs for destructive operations
- Clear error messages

## Technology Stack

**Frontend:**
- React 18 with TypeScript
- TanStack Query for server state management
- Zustand for client state
- shadcn/ui components (Radix UI + Tailwind CSS)
- React Router v6
- Axios for HTTP requests
- oidc-client-ts for OIDC authentication

**Build Tool:**
- Vite (faster development and builds)

**UI Components:**
- Recharts for visualizations
- Custom components for dashboard-specific UI

## Navigation Structure

**Top Navigation Bar:**
```
[Logo] Runner Token Service    [Search]  [User] [Settings]
```

**Sidebar Navigation:**
```
Dashboard
Runners
─────────────    [Admin-only section]
Label Policies
Security Events
Admin Console
─────────────    [Common section]
Audit Log
Settings
```

## Page Structure

### Home / Dashboard Page

**Content:**
- Overview statistics (total, active, offline, pending runners)
- [Admin Only] Top users by runner count
- Recent activity feed
- Quick action button: "+ Provision Runner"

**Features:**
- Stat cards with visual indicators
- Bar chart showing runner distribution
- Activity feed with timestamps
- Primary CTA for provisioning

### Runners List Page

**Layout:**
- Filters: Status, User (admin only), Labels
- Search box (debounced)
- Bulk selection (admin only)
- Table with columns: Name, Status, User, Labels, Actions

**Features:**
- Sorting by name, status, created date
- Pagination with configurable page size
- Row actions menu: View Details, Refresh Status, Deprovision
- Bulk deprovision (admin only)
- Export to CSV/JSON

### Runner Detail Page

**Content:**
- Runner metadata (name, status, ID, labels, ephemeral flag)
- Provisioning details (by whom, when)
- GitHub link
- Action buttons: Refresh Status, Deprovision, View in GitHub
- Activity timeline

### Label Policies Page (Admin Only)

**Content:**
- List of label policies
- For each: User, allowed labels, max runners
- Create/Edit/Delete policy modals
- Search and filter

### Security Events Page (Admin Only)

**Content:**
- List of security events
- Filters: Type, Severity, User, Date range
- Event detail view
- Export capability

### Audit Log Page

**Content:**
- Audit log viewer (admin: all, user: own)
- Filters: Event type, User, Date range, Status
- Pagination
- Export to JSON

## Authentication Flow

```
1. Browser accesses Dashboard
2. Redirect to OIDC Provider (Auth0, Okta, etc.)
3. User authenticates
4. OIDC Provider redirects to Dashboard with auth code
5. Dashboard exchanges code for ID + Access tokens
6. Dashboard stores tokens securely (httpOnly cookie)
7. Dashboard renders UI based on user role
8. All API calls include Authorization: Bearer {access_token}
```

## API Integration

**Dashboard-specific endpoints:**
- `GET /api/v1/dashboard/stats` - Overview statistics
- `GET /api/v1/dashboard/activity` - Recent activity feed
- `GET /api/v1/runners?filter=...` - List runners (existing)
- `GET /api/v1/admin/security-events` - Security events list
- `GET /api/v1/admin/policies` - Label policies list

**Uses existing endpoints:**
- `POST /api/v1/runners/provision` - Provision runner
- `POST /api/v1/runners/{id}/refresh` - Refresh status
- `DELETE /api/v1/runners/{id}` - Deprovision runner

## Status Indicators

**Runner Status Colors:**
- 🟢 **Active** - Green (#28a745)
- 🔴 **Offline** - Red (#dc3545)
- 🟡 **Pending** - Amber (#ffc107)
- ⚫ **Deleted** - Gray (#6c757d)

## Implementation Notes

### State Management

**Server State (TanStack Query):**
- Runner lists
- Policy lists
- Security events
- User profile

**Client State (Zustand):**
- UI state (sidebar open/closed, selected filters)
- User preferences (page size, sort order)
- Search state

### Error Handling

- Validation errors: Display field-specific errors in forms
- API errors: Show toast notifications
- Authentication errors: Redirect to login
- Permission errors: Show "Access Denied" message

### Loading States

- Skeleton loaders for initial data load
- Spinner overlays for async operations
- Disable buttons during async operations

### Mobile Responsiveness

- Collapse sidebar on mobile
- Stack table columns (convert to card view on mobile)
- Reduce padding/spacing on small screens
- Full-width modals on mobile

## Future Enhancements

1. **Real-time Updates**: WebSocket for live runner status
2. **Notifications**: Toast notifications for runner status changes
3. **Export Scheduling**: Schedule reports to be emailed
4. **Runner Templates**: Save and reuse runner configurations
5. **Webhooks Management**: Configure GitHub webhooks from dashboard
6. **API Token Management**: Generate and manage API tokens for programmatic access
