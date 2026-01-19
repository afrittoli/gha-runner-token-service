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

### Current Limitations

1. **No authentication** - Dashboard is publicly accessible
2. **No real-time updates** - Manual page refresh required
3. **Read-only** - No runner management actions
4. **Shows OIDC sub, not email** - User display name issue (depends on user provisioning feature)

---

## Future: Full Dashboard Specification

The sections below describe a comprehensive dashboard implementation for future development. It is divided into two phases:
- **Phase 1 MVP:** Core functionality with basic admin features
- **Phase 2+:** Advanced features with real-time updates and enhanced admin capabilities

### Executive Summary

The full dashboard is a web-based administrative interface that provides authenticated access to runner management operations with role-based access control distinguishing administrative and standard user capabilities.

**Key Goals:**
- Provide intuitive UI for runner management (provision, view, delete)
- Enable administrators to manage all runners and enforce policies
- Restrict standard users to viewing/managing their own runners
- Support filtering, searching, and bulk operations
- Real-time status updates for immediate feedback

---

### Functional Requirements

#### Authentication & Authorization

- **OIDC-based authentication** (reusing service's existing OIDC configuration)
- **Role-based access control (RBAC)** distinguishing Admin vs. Standard User
- **Session management** with token refresh and security
- **Admin role assignment mechanism** (via OIDC claims or admin_users table)

#### Admin Capabilities

- View all provisioned runners across all users
- Filter/search runners by user, status, labels
- Deprovision individual runners
- Bulk deprovision operations (all runners for a user, all offline runners, by label)
- View and manage label policies
- Query security events and view audit logs
- System health monitoring
- User management and role assignment

#### Standard User Capabilities

- View own provisioned runners only
- Read-only access to runner status
- No deprovisioning capabilities (enforced via API)
- View own audit trail
- Provision new runners

#### Core Features

- Real-time runner status updates (WebSocket or polling)
- Pagination for large datasets
- Export functionality (CSV, JSON)
- Responsive design (desktop, tablet, mobile)
- Global search across runners, labels, users
- Advanced filtering and sorting

### Non-Functional Requirements

#### Performance

- Initial page load: <2 seconds
- API response rendering: <500ms
- Support 100+ concurrent users
- Efficient pagination (100 items per page)

#### Security

- All API calls authenticated via OIDC token
- CSRF protection
- XSS prevention (input sanitization, CSP headers)
- Secure session storage (httpOnly cookies)
- Backend RBAC enforcement (non-negotiable)
- Token management strategy for sensitive data

#### Usability

- Intuitive navigation
- Accessible (WCAG 2.1 AA compliance)
- Confirmation dialogs for destructive operations
- Clear error messages and status feedback

---

### Technical Architecture

#### Recommended Technology Stack

**Frontend Framework:**
- **React 18** with TypeScript (component reusability, type safety, large ecosystem)
- **Alternative:** Svelte (lighter) or Vue.js (simpler)

**State Management:**
- **TanStack Query (React Query)** for server state (caching, invalidation, refetching)
- **Zustand** for client state (user preferences, UI state)
- **Alternative:** Redux Toolkit for more centralized state

**UI Component Library:**
- **shadcn/ui** (Radix UI + Tailwind CSS) - accessible by default, customizable, tree-shakeable
- **Alternative:** Material UI or Ant Design

**HTTP Client:**
- **Axios** with interceptors for authentication
- **Authentication:** oidc-client-ts (industry-standard OIDC library)

**Build Tool:**
- **Vite** (faster than webpack, optimal for React)

**Real-Time Updates:**
- **WebSocket** via Socket.io or native WebSocket API
- **Fallback:** Polling every 30 seconds if WebSocket unavailable

**Charts/Visualization:**
- **Recharts** (declarative, React-friendly)

**Testing:**
- Jest + React Testing Library (unit/integration)
- Playwright (e2e)

#### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Web Dashboard                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Browser (React SPA)                               │  │
│  │  ┌─────────────┐ ┌──────────────┐ ┌─────────┐   │  │
│  │  │ OIDC Client │ │ React Router │ │ UI Comp │   │  │
│  │  │ (Auth)      │ │ (Navigation) │ │ Library │   │  │
│  │  └──────┬──────┘ └──────┬───────┘ └────┬────┘   │  │
│  │         │                │              │        │  │
│  │  ┌──────▼────────────────▼──────────────▼─────┐  │  │
│  │  │     API Client (Axios + React Query)       │  │  │
│  │  │     WebSocket Client (Real-time updates)   │  │  │
│  │  └──────────────────┬─────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
│                      │ HTTPS + Bearer Token            │
└──────────────────────┼────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│           Runner Token Service (Backend)               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ FastAPI API                                      │  │
│  │ - /api/v1/runners/*                             │  │
│  │ - /api/v1/admin/*                               │  │
│  │ - /api/v1/dashboard/* (new endpoints)           │  │
│  │ - WS /api/v1/ws (WebSocket for real-time)       │  │
│  └──────────┬───────────────────────────────────────┘  │
└─────────────┼──────────────────────────────────────────┘
              ▼
    ┌─────────────────────┐
    │   Database (SQLite) │
    │   or PostgreSQL     │
    └─────────────────────┘
```

#### Authentication Flow

```
┌────────┐              ┌──────────┐           ┌─────────────┐
│Browser │              │Dashboard │           │OIDC Provider│
└───┬────┘              └────┬─────┘           └──────┬──────┘
    │                        │                       │
    │ 1. Access Dashboard    │                       │
    ├─────────────────────>  │                       │
    │                        │                       │
    │ 2. Redirect to OIDC    │                       │
    │<─────────────────────  ├──────────────────>    │
    │                        │   3. Authenticate    │
    │                        │<──────────────────────┤
    │<────────────────────────────── Auth Code ─────┤
    │                        │                       │
    │ 4. Send Auth Code      │                       │
    ├─────────────────────>  ├────── Exchange ──>    │
    │                        │     Code & Secret    │
    │                        │<──── Token ──────────┤
    │ 5. Store Token + Load  │                       │
    │<─────────────────────  │                       │
    │                        │                       │
    │ 6. API Calls           │                       │
    │    (Bearer Token)      │                       │
    ├─────────────────────>  │                       │
    │                        ├──── Verify Token ───>│
    │                        │<──── Valid ──────────┤
    │                        │                       │
```

---

### Page Structure & Site Map

#### Sitemap

```
Dashboard
├── Home (/)
│   ├── Overview Statistics
│   ├── Recent Activity
│   └── Quick Actions
│
├── Runners (/runners)
│   ├── List View (table with filters)
│   ├── Detail View (/runners/:id)
│   └── Provision Runner (modal/page)
│
├── Label Policies (/policies) [Admin Only]
│   ├── List View
│   ├── Create/Edit (modal/page)
│   └── Policy Detail
│
├── Security Events (/security) [Admin Only]
│   ├── Event List
│   ├── Event Detail
│   └── Filters/Export
│
├── Audit Log (/audit)
│   ├── Log Viewer (Admin: all, User: own)
│   └── Export
│
├── Settings (/settings)
│   ├── User Profile
│   ├── Preferences
│   └── API Tokens (future)
│
└── Admin (/admin) [Admin Only]
    ├── User Management
    ├── System Health
    └── Configuration
```

#### Navigation Structure

**Top Navigation Bar:**
```
┌────────────────────────────────────────────────────────────┐
│ [Logo] Runner Token Service    [Search]  [User]  [Settings]│
└────────────────────────────────────────────────────────────┘
```

**Sidebar Navigation:**
```
┌──────────────────┐
│ Dashboard        │
│ Runners          │
│ ─────────────    │ [Admin-only section]
│ Label Policies   │
│ Security Events  │
│ Admin Console    │
│ ─────────────    │ [Common section]
│ Audit Log        │
│ Settings         │
└──────────────────┘
```

---

### Page Designs

#### 4.1 Home / Dashboard Page

**Layout:**
```
┌────────────────────────────────────────────────────────┐
│ Dashboard Overview                                     │
├────────────────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │
│ │ Total   │ │ Active  │ │ Offline │ │ Pending │      │
│ │ Runners │ │ Runners │ │ Runners │ │ Runners │      │
│ │   42    │ │   38    │ │   3     │ │   1     │      │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘      │
│                                                        │
│ [Admin Only: Stats by User]                           │
│ ┌──────────────────────────────────────────────────┐  │
│ │ Top Users by Runner Count                        │  │
│ │ alice@example.com    ████████████ 12 runners    │  │
│ │ bob@example.com      ████████ 8 runners         │  │
│ │ carol@example.com    ████ 4 runners             │  │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ Recent Activity                                       │
│ ┌──────────────────────────────────────────────────┐  │
│ │ 2m ago   alice provisioned runner-01             │  │
│ │ 15m ago  bob deprovisioned runner-02             │  │
│ │ 1h ago   System cleaned up 3 stale runners       │  │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ [+ Provision Runner]                                 │
└────────────────────────────────────────────────────────┘
```

**Components:**
- Stat cards with icons
- Bar chart for user distribution
- Activity feed with timestamps
- Quick action button

#### 4.2 Runners List Page

**Layout:**
```
┌────────────────────────────────────────────────────────┐
│ Runners                                                │
│ ┌──────────┐  ┌─────────────┐  [+ Provision Runner]   │
│ │ Filters ▼│  │  Search...  │                         │
│ └──────────┘  └─────────────┘                         │
├────────────────────────────────────────────────────────┤
│ Active Filters: [Status: Active ×] [User: alice ×]    │
├────────────────────────────────────────────────────────┤
│ [Admin View: Bulk Actions]                            │
│ [☐] Select All  | Deprovision Selected (5)            │
├─────┬────────────┬────────┬──────────┬────────┬───────┤
│ Sel │ Name       │ Status │ User     │ Labels │ Action│
├─────┼────────────┼────────┼──────────┼────────┼───────┤
│ ☐   │ runner-001 │ 🟢 Act │ alice@.. │ linux  │ [⋮]  │
│ ☐   │ runner-002 │ 🔴 Off │ bob@..   │ gpu    │ [⋮]  │
│ ☐   │ runner-003 │ 🟡 Pen │ carol@.. │ docker │ [⋮]  │
└─────┴────────────┴────────┴──────────┴────────┴───────┘
│ Showing 1-10 of 42    [< Prev] [1][2][3][4] [Next >]  │
└────────────────────────────────────────────────────────┘
```

**Features:**
- Search (debounced, searches name, labels, user)
- Filters (status, user, labels, ephemeral)
- Sorting (by name, status, created date)
- Bulk selection (admin only)
- Row actions: View Details, Refresh Status, Deprovision
- Pagination
- Export button (CSV/JSON)

#### 4.3 Runner Detail Page

**Layout:**
```
┌────────────────────────────────────────────────────────┐
│ ← Back to Runners                                      │
│                                                        │
│ runner-001                        [🟢 Active]         │
│ ─────────────────────────────────────────────────────  │
│                                                        │
│ Details                                                │
│ ┌──────────────────────────────────────────────────┐  │
│ │ Name:            runner-001                      │  │
│ │ Status:          Active                          │  │
│ │ Provisioned by:  alice@example.com               │  │
│ │ GitHub ID:       123456                          │  │
│ │ Labels:          [linux] [docker] [team-a]       │  │
│ │ Ephemeral:       Yes                             │  │
│ │ Created:         2026-01-16 14:30:00 UTC         │  │
│ │ Registered:      2026-01-16 14:31:23 UTC         │  │
│ │ Last Seen:       2026-01-16 18:45:12 UTC         │  │
│ └──────────────────────────────────────────────────┘  │
│                                                        │
│ Actions                                                │
│ [Refresh Status] [Deprovision Runner] [View in GH]    │
│                                                        │
│ Activity Timeline                                      │
│ ┌──────────────────────────────────────────────────┐  │
│ │ ● 2026-01-16 14:31 - Registered with GitHub      │  │
│ │ ● 2026-01-16 14:30 - Provisioned by alice        │  │
│ └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

#### 4.4 Label Policies (Admin Only)

**Layout:**
```
┌────────────────────────────────────────────────────────┐
│ Label Policies                   [+ Create Policy]     │
│ ┌─────────────┐                                        │
│ │  Search...  │                                        │
│ └─────────────┘                                        │
├─────┬──────────────┬──────────────┬─────────┬──────────┤
│ User             │ Allowed Labels│ Max     │ Actions  │
│                  │ & Patterns    │ Runners │          │
├──────────────────┼───────────────┼─────────┼──────────┤
│alice@example.com │ team-a, linux │ 10      │ [Edit]   │
│                  │ team-a-.*     │         │ [Delete] │
├──────────────────┼───────────────┼─────────┼──────────┤
│bob@example.com   │ gpu, cuda     │ 5       │ [Edit]   │
│                  │ gpu-.*        │         │ [Delete] │
└──────────────────┴───────────────┴─────────┴──────────┘
│ Showing 1-10 of 25    [< Prev] [1][2][3] [Next >]     │
└────────────────────────────────────────────────────────┘
```

#### 4.5 Security Events (Admin Only)

**Layout:**
```
┌────────────────────────────────────────────────────────┐
│ Security Events                                        │
│ ┌──────────┐  ┌──────────┐  ┌─────────────┐ [Export]  │
│ │ Type ▼   │  │Severity ▼│  │  Search...  │           │
│ └──────────┘  └──────────┘  └─────────────┘           │
├────────────────────────────────────────────────────────┤
│ Active Filters: [Severity: High ×]                     │
├──────────┬────────────┬─────────┬──────────┬──────────┤
│ Time     │ Type       │Severity │ User     │ Details  │
├──────────┼────────────┼─────────┼──────────┼──────────┤
│ 2m ago   │ Label Viol │ 🔴 HIGH │ alice@.. │ [View]   │
│ 15m ago  │ Quota Exc  │ 🟡 LOW  │ bob@..   │ [View]   │
│ 1h ago   │ Label Viol │ 🟠 MED  │ carol@..│ [View]   │
└──────────┴────────────┴─────────┴──────────┴──────────┘
│ Showing 1-20 of 150   [< Prev] [1][2][3] [Next >]    │
└────────────────────────────────────────────────────────┘
```

#### 4.6 Provision Runner Flow

**Modal:**
```
┌────────────────────────────────────────────┐
│ Provision New Runner             [×]      │
├────────────────────────────────────────────┤
│ Runner Name *                              │
│ [worker-001                     ]          │
│                                            │
│ Labels *                                   │
│ [linux                     ] [+ Add]       │
│ [docker                    ] [× Remove]    │
│                                            │
│ ☑ Ephemeral (auto-delete after job)       │
│ ☐ Disable automatic updates               │
│                                            │
│ Runner Group                               │
│ [Default ▼                            ]    │
│                                            │
│ [Cancel]             [Provision]          │
└────────────────────────────────────────────┘
```

**Success Modal:**
```
┌────────────────────────────────────────────┐
│ Runner Provisioned Successfully! [×]       │
├────────────────────────────────────────────┤
│ Your runner registration token:            │
│                                            │
│ ┌──────────────────────────────────────┐  │
│ │ AABBCCDD123456789...      [📋]       │  │
│ └──────────────────────────────────────┘  │
│                                            │
│ ⚠ This token expires in 1 hour             │
│                                            │
│ Configuration Command:                    │
│ ┌──────────────────────────────────────┐  │
│ │ ./config.sh \           [📋]         │  │
│ │   --url https://github.com/org \     │  │
│ │   --token AABBCCDD... \              │  │
│ │   --name worker-001 \                │  │
│ │   --labels linux,docker \            │  │
│ │   --ephemeral                        │  │
│ └──────────────────────────────────────┘  │
│                                            │
│ [View Runner]        [Done]                │
└────────────────────────────────────────────┘
```

---

### Additional Features (Phase 2+)

#### Real-Time Updates

**WebSocket Integration:**
- Connection to backend via WebSocket for live updates
- Events: runner status change, new runner, runner deleted, security events
- Toast notifications for important events
- Fallback: Polling every 30 seconds if WebSocket unavailable

#### Bulk Operations (Admin)

**Deprovision Multiple Runners:**
- Deprovision all runners for a user
- Deprovision all offline runners
- Deprovision all runners with specific label
- Confirmation dialog with typed confirmation

#### Export Functionality

**Export Options:**
- Format: CSV, JSON, Excel (XLSX)
- Include: runner details, labels, status, timestamps
- Apply current filters to export

#### Search

**Global Search (in nav bar):**
- Searches: runner names, labels, users
- Shows results grouped by type
- Quick navigation to detail pages

#### User Preferences

**Settings Page:**
- Theme: Light / Dark / Auto
- Timezone: Select from list
- Date Format: Choose format
- Items per page: Pagination size
- Notifications: Email/browser notifications preferences

#### System Health (Admin)

**Monitoring Dashboard:**
- Service status and uptime
- Component health (API, Database, GitHub, OIDC)
- Metrics (requests, runners, response time, error rate)
- View logs and metrics

---

### API Requirements (Backend Additions)

#### New Endpoints

**Dashboard Statistics:**
```
GET /api/v1/dashboard/stats
Response:
{
  "total_runners": 42,
  "active_runners": 38,
  "offline_runners": 3,
  "pending_runners": 1,
  "runners_by_user": [...],
  "recent_activity": [...]
}
```

**Admin Role Check:**
```
GET /api/v1/auth/me
Response:
{
  "identity": "alice@example.com",
  "email": "alice@example.com",
  "roles": ["admin"],
  "permissions": ["runners:read", "runners:write", "policies:manage"]
}
```

**WebSocket Endpoint:**
```
WS /api/v1/ws
- Requires Bearer token in handshake
- Broadcasts runner status changes
- Broadcasts security events (admin only)
```

#### Enhanced Existing Endpoints

**Runners List - Add Query Parameters:**
```
GET /api/v1/runners?user=alice@example.com&status=active&labels=linux&page=1&limit=100&sort=created_at:desc
```

**Bulk Operations:**
```
POST /api/v1/admin/runners/bulk-deprovision
Body:
{
  "runner_ids": ["id1", "id2", "id3"],
  "reason": "Cleanup offline runners"
}
```

---

### Security Considerations

#### Authentication & Authorization

**OIDC Token Management:**
- Store access token in memory (React state)
- Store refresh token in httpOnly cookie
- Implement token refresh logic
- Clear tokens on logout

**RBAC Enforcement:**
- **Frontend:** Check admin role on UI level (UI hiding)
- **Backend:** ENFORCE on every endpoint (critical for security)
- Admin endpoints return 403 for non-admin users

#### XSS Prevention

- All user inputs sanitized with DOMPurify
- React's built-in XSS protection
- Content Security Policy headers

#### CSRF Protection

- Not vulnerable to traditional CSRF (Bearer tokens, not cookies)
- Use Bearer tokens in Authorization header
- Refresh token in httpOnly cookie with SameSite=Strict

#### Sensitive Data Handling

**Registration Tokens:**
- Display once in modal
- Mask in logs: `AAA...789` (first 3 + last 3 chars)
- Copy to clipboard with notification
- Clear from state after modal close

**Session Storage:**
- No sensitive data in localStorage
- Access token in memory only
- Refresh token in httpOnly cookie

---

### Implementation Phases

#### Phase 1: MVP (Core Functionality) - 4-6 weeks
- OIDC authentication
- Home dashboard (basic stats)
- Runners list (read-only)
- Runner detail view
- Provision runner flow
- Basic admin role check
- Responsive layout
- **Token Estimate:** ~15,000

#### Phase 2: Admin Features - 3-4 weeks
- Label policies management
- Security events viewer
- Bulk operations
- Audit log viewer
- Admin console
- **Token Estimate:** ~10,000

#### Phase 3: Real-Time & Polish - 2-3 weeks
- WebSocket integration
- Real-time status updates
- Toast notifications
- Search functionality
- Export functionality
- **Token Estimate:** ~8,000

#### Phase 4: Advanced Features - 2-3 weeks
- User preferences
- System health monitoring
- Advanced filtering
- E2E testing
- **Token Estimate:** ~7,000

**Grand Total: ~40,500 tokens (300-365 hours, 2-3 months full-time)**

---

### Status Indicators

| Status | Color | Hex |
|--------|-------|-----|
| Active | Green | #28a745 |
| Offline | Red | #dc3545 |
| Pending | Amber | #ffc107 |
| Deleted | Gray | #6c757d |

### Implementation Recommendations

1. **Backend Priority:** Implement admin role system FIRST (critical for security)
2. **MVP Scope:** Start with Phase 1 only, gather user feedback
3. **Technology:** Use React + TypeScript, shadcn/ui, TanStack Query
4. **Security:** Backend RBAC is non-negotiable; token management strategy before coding
5. **De-Risking:** Prototype authentication flow first, decide on WebSocket vs polling early

---

## Summary

**Current State:** Basic Jinja2 dashboard with limited functionality, no auth, no real-time updates

**Vision:** Full-featured React SPA with OIDC auth, real-time updates, comprehensive admin tools, and role-based access control

**Path Forward:** Implement backend RBAC first, then build Phase 1 MVP with core functionality, gather feedback, iterate with Phase 2+

4. Add label policy management UI
5. Add security events viewer
6. Consider React migration if complexity warrants
