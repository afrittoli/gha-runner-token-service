# Runner Token Service - Web Dashboard Design

## Executive Summary

This document specifies the design for a web-based administrative dashboard for the GitHub Runner Token Service. The dashboard provides authenticated access to runner management operations with role-based access control distinguishing administrative and standard user capabilities.

---

## 1. Requirements Analysis

### 1.1 Functional Requirements

**Authentication & Authorization:**
- OIDC-based authentication (reusing service's existing OIDC configuration)
- Role-based access control (Admin vs. Standard User)
- Admin role assignment mechanism
- Session management with token refresh

**Admin Capabilities:**
- View all provisioned runners across all users
- Filter/search runners by user, status, labels
- Deprovision individual runners
- Bulk deprovision operations (all runners for a user, all offline runners)
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

### 1.2 Non-Functional Requirements

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

---

## 2. Technical Architecture

### 2.1 Technology Stack

**Frontend Framework:**
- **React 18** with TypeScript
  - Rationale: Component reusability, type safety, large ecosystem
  - Alternatives considered: Vue.js (simpler), Svelte (smaller bundle)

**State Management:**
- **TanStack Query (React Query)** for server state
  - Handles caching, invalidation, background refetching
- **Zustand** for client state (user preferences, UI state)
  - Lightweight, simple API

**UI Component Library:**
- **shadcn/ui** (Radix UI + Tailwind CSS)
  - Accessible by default
  - Customizable
  - Tree-shakeable

**Routing:**
- **React Router v6**

**HTTP Client:**
- **Axios** with interceptors for authentication

**Build Tool:**
- **Vite** (faster than webpack, optimal for React)

**Authentication:**
- **oidc-client-ts** (industry-standard OIDC library)

**Charts/Visualization:**
- **Recharts** (declarative, React-friendly)

**Testing:**
- Jest + React Testing Library (unit/integration)
- Playwright (e2e)

### 2.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Web Dashboard                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Browser (React SPA)                              │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────┐  │  │
│  │  │ OIDC Client │  │ React Router │  │ UI      │  │  │
│  │  │ (Auth)      │  │ (Navigation) │  │ Comps   │  │  │
│  │  └──────┬──────┘  └──────┬───────┘  └────┬────┘  │  │
│  │         │                │               │        │  │
│  │  ┌──────▼────────────────▼───────────────▼─────┐  │  │
│  │  │      API Client (Axios + React Query)      │  │  │
│  │  └──────────────────┬─────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTPS + Bearer Token
                      ▼
┌─────────────────────────────────────────────────────────┐
│           Runner Token Service (Backend)                │
│  ┌──────────────────────────────────────────────────┐   │
│  │  FastAPI API                                     │   │
│  │  - /api/v1/runners/*                             │   │
│  │  - /api/v1/admin/*                               │   │
│  │  - /api/v1/dashboard/* (new endpoints)           │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Authentication Flow

```
┌────────┐                ┌──────────┐               ┌─────────────┐
│Browser │                │Dashboard │               │OIDC Provider│
└───┬────┘                └────┬─────┘               └──────┬──────┘
    │                          │                            │
    │ 1. Access Dashboard      │                            │
    ├─────────────────────────>│                            │
    │                          │                            │
    │ 2. Redirect to OIDC      │                            │
    │<─────────────────────────┤                            │
    │                          │                            │
    │ 3. Authenticate          │                            │
    ├────────────────────────────────────────────────────────>
    │                          │                            │
    │ 4. Authorization Code    │                            │
    │<────────────────────────────────────────────────────────
    │                          │                            │
    │ 5. Code + Redirect       │                            │
    ├─────────────────────────>│                            │
    │                          │                            │
    │                          │ 6. Exchange Code for Token │
    │                          ├───────────────────────────>│
    │                          │                            │
    │                          │ 7. ID Token + Access Token │
    │                          │<───────────────────────────┤
    │                          │                            │
    │ 8. Store Token + Load UI │                            │
    │<─────────────────────────┤                            │
    │                          │                            │
    │ 9. API Calls             │                            │
    │ (Bearer: Access Token)   │                            │
    ├─────────────────────────>│                            │
```

---

## 3. Page Structure & Navigation

### 3.1 Site Map

```
Dashboard
├── Home (/)
│   ├── Overview Statistics
│   ├── Recent Activity
│   └── Quick Actions
│
├── Runners (/runners)
│   ├── List View (table)
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

### 3.2 Navigation Structure

**Top Navigation Bar:**
```
┌────────────────────────────────────────────────────────────┐
│ [Logo] Runner Token Service    [Search]  [User] [Settings]│
└────────────────────────────────────────────────────────────┘
```

**Sidebar Navigation:**
```
┌──────────────────┐
│ Dashboard        │
│ Runners          │
│ ─────────────    │  [Admin-only section]
│ Label Policies   │
│ Security Events  │
│ Admin Console    │
│ ─────────────    │  [Common section]
│ Audit Log        │
│ Settings         │
└──────────────────┘
```

---

## 4. Page Designs

### 4.1 Home / Dashboard Page

**Layout:**
```
┌────────────────────────────────────────────────────────┐
│  Dashboard Overview                                    │
├────────────────────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │
│  │ Total   │ │ Active  │ │ Offline │ │ Pending │     │
│  │ Runners │ │ Runners │ │ Runners │ │ Runners │     │
│  │   42    │ │   38    │ │    3    │ │    1    │     │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘     │
│                                                        │
│  [Admin Only: Stats by User]                          │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Top Users by Runner Count                        │ │
│  │ alice@example.com    ████████████ 12 runners    │ │
│  │ bob@example.com      ████████ 8 runners         │ │
│  │ carol@example.com    ████ 4 runners             │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Recent Activity                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │ 2m ago  alice@example.com provisioned runner-01 │ │
│  │ 15m ago bob@example.com deprovisioned runner-02 │ │
│  │ 1h ago  System cleaned up 3 stale runners       │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  [Quick Actions Button: + Provision Runner]           │
└────────────────────────────────────────────────────────┘
```

**Components:**
- Stat cards with icons
- Bar chart (Chart.js or Recharts)
- Activity feed with timestamps
- Action button (primary CTA)

### 4.2 Runners List Page

**Layout:**
```
┌────────────────────────────────────────────────────────┐
│  Runners                                               │
│  ┌──────────┐  ┌─────────────┐  [+ Provision Runner] │
│  │ Filters ▼│  │  Search...  │                        │
│  └──────────┘  └─────────────┘                        │
├────────────────────────────────────────────────────────┤
│  Active Filters: [Status: Active ×] [User: alice ×]   │
├────────────────────────────────────────────────────────┤
│  [Admin View: Bulk Actions]                            │
│  [☐] Select All  | Deprovision Selected (5)           │
├─────┬────────────┬────────┬──────────┬────────┬───────┤
│ Sel │ Name       │ Status │ User     │ Labels │ Action│
├─────┼────────────┼────────┼──────────┼────────┼───────┤
│ ☐   │ runner-001 │ 🟢 Act │ alice@.. │ linux  │ [⋮]  │
│ ☐   │ runner-002 │ 🔴 Off │ bob@..   │ gpu    │ [⋮]  │
│ ☐   │ runner-003 │ 🟡 Pen │ carol@.. │ docker │ [⋮]  │
└─────┴────────────┴────────┴──────────┴────────┴───────┘
│  Showing 1-10 of 42    [< Prev] [1][2][3][4] [Next >] │
└────────────────────────────────────────────────────────┘
```

**Features:**
- Search (debounced, searches name, labels, user)
- Filters (status, user, labels, ephemeral)
- Sorting (by name, status, created date)
- Bulk selection (admin only)
- Row actions menu (⋮): View Details, Refresh Status, Deprovision
- Pagination
- Export button (CSV/JSON)

**Filter Dropdown:**
```
┌──────────────────────┐
│ Filter Runners       │
├──────────────────────┤
│ Status               │
│ ☐ Active             │
│ ☐ Offline            │
│ ☐ Pending            │
│ ☐ Deleted            │
├──────────────────────┤
│ User (Admin Only)    │
│ [Search users...]    │
│ ☐ alice@example.com  │
│ ☐ bob@example.com    │
├──────────────────────┤
│ Labels               │
│ ☐ linux              │
│ ☐ gpu                │
│ ☐ docker             │
├──────────────────────┤
│ [Clear] [Apply]      │
└──────────────────────┘
```

### 4.3 Runner Detail Page

```
┌────────────────────────────────────────────────────────┐
│  ← Back to Runners                                     │
│                                                        │
│  runner-001                        [🟢 Active]        │
│  ───────────────────────────────────────────────────  │
│                                                        │
│  Details                                               │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Name:           runner-001                       │ │
│  │ Status:         Active                           │ │
│  │ Provisioned by: alice@example.com                │ │
│  │ GitHub ID:      123456                           │ │
│  │ Labels:         [linux] [docker] [team-a]       │ │
│  │ Ephemeral:      Yes                              │ │
│  │ Created:        2026-01-16 14:30:00 UTC          │ │
│  │ Registered:     2026-01-16 14:31:23 UTC          │ │
│  │ Last Seen:      2026-01-16 18:45:12 UTC          │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  Actions                                               │
│  [Refresh Status] [Deprovision Runner] [View in GH]  │
│                                                        │
│  Activity Timeline                                     │
│  ┌──────────────────────────────────────────────────┐ │
│  │ ● 2026-01-16 14:31 - Registered with GitHub     │ │
│  │ ● 2026-01-16 14:30 - Provisioned by alice       │ │
│  └──────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────┘
```

### 4.4 Label Policies Page (Admin Only)

```
┌────────────────────────────────────────────────────────┐
│  Label Policies                   [+ Create Policy]    │
│  ┌─────────────┐                                       │
│  │  Search...  │                                       │
│  └─────────────┘                                       │
├─────┬──────────────┬─────────────┬─────────┬──────────┤
│ User             │ Allowed      │ Max     │ Actions  │
│                  │ Labels       │ Runners │          │
├──────────────────┼──────────────┼─────────┼──────────┤
│ alice@example.com│ team-a,linux │ 10      │ [Edit]   │
│                  │ team-a-.*    │         │ [Delete] │
├──────────────────┼──────────────┼─────────┼──────────┤
│ bob@example.com  │ gpu, cuda    │ 5       │ [Edit]   │
│                  │ gpu-.*       │         │ [Delete] │
└──────────────────┴──────────────┴─────────┴──────────┘
│  Showing 1-10 of 25    [< Prev] [1][2][3] [Next >]   │
└────────────────────────────────────────────────────────┘
```

**Create/Edit Policy Modal:**
```
┌────────────────────────────────────────────┐
│  Create Label Policy              [×]      │
├────────────────────────────────────────────┤
│  User Identity *                           │
│  [alice@example.com                    ]   │
│                                            │
│  Allowed Labels *                          │
│  [team-a                    ] [+ Add]      │
│  [linux                     ] [× Remove]   │
│  [docker                    ] [× Remove]   │
│                                            │
│  Label Patterns (Regex)                    │
│  [team-a-.*                 ] [+ Add]      │
│                                            │
│  Max Concurrent Runners                    │
│  [10                        ]              │
│                                            │
│  Description                               │
│  [Team A development runners____________]  │
│  [______________________________________]  │
│                                            │
│  [Cancel]              [Create Policy]     │
└────────────────────────────────────────────┘
```

### 4.5 Security Events Page (Admin Only)

```
┌────────────────────────────────────────────────────────┐
│  Security Events                                       │
│  ┌──────────┐  ┌──────────┐  ┌─────────────┐  [Export]
│  │ Type   ▼ │  │ Severity▼│  │  Search...  │         │
│  └──────────┘  └──────────┘  └─────────────┘         │
├────────────────────────────────────────────────────────┤
│  Active Filters: [Severity: High ×]                    │
├──────────┬────────────┬─────────┬──────────┬──────────┤
│ Time     │ Type       │ Severity│ User     │ Details  │
├──────────┼────────────┼─────────┼──────────┼──────────┤
│ 2m ago   │ Label Viol │ 🔴 HIGH │ alice@.. │ [View]   │
│ 15m ago  │ Quota Exc  │ 🟡 LOW  │ bob@..   │ [View]   │
│ 1h ago   │ Label Viol │ 🟠 MED  │ carol@.. │ [View]   │
└──────────┴────────────┴─────────┴──────────┴──────────┘
│  Showing 1-20 of 150    [< Prev] [1][2][3] [Next >]   │
└────────────────────────────────────────────────────────┘
```

**Event Detail Modal:**
```
┌────────────────────────────────────────────┐
│  Security Event #12345           [×]       │
├────────────────────────────────────────────┤
│  Event Type:    Label Policy Violation     │
│  Severity:      🔴 HIGH                    │
│  User:          alice@example.com          │
│  Runner:        runner-001                 │
│  Timestamp:     2026-01-16 18:45:12 UTC    │
│                                            │
│  Violation Details:                        │
│  ┌──────────────────────────────────────┐ │
│  │ Expected labels: ["team-a", "linux"] │ │
│  │ Actual labels:   ["team-a", "gpu"]   │ │
│  │ Mismatched:      ["gpu"]             │ │
│  │ Method:          post_registration   │ │
│  └──────────────────────────────────────┘ │
│                                            │
│  Action Taken:   Runner Deleted            │
│                                            │
│  [Close]                                   │
└────────────────────────────────────────────┘
```

### 4.6 Provision Runner Flow

**Option A: Modal**
```
┌────────────────────────────────────────────┐
│  Provision New Runner             [×]      │
├────────────────────────────────────────────┤
│  Runner Name *                             │
│  [worker-001                           ]   │
│                                            │
│  Labels *                                  │
│  [linux                     ] [+ Add]      │
│  [docker                    ] [× Remove]   │
│                                            │
│  ☑ Ephemeral (auto-delete after one job)  │
│  ☐ Disable automatic updates               │
│                                            │
│  Runner Group                              │
│  [Default ▼                            ]   │
│                                            │
│  [Cancel]              [Provision]         │
└────────────────────────────────────────────┘
```

**Success Modal:**
```
┌────────────────────────────────────────────┐
│  Runner Provisioned Successfully! [×]      │
├────────────────────────────────────────────┤
│  Your runner registration token:           │
│                                            │
│  ┌──────────────────────────────────────┐ │
│  │ AABBCCDD123456789...              [📋]│ │
│  └──────────────────────────────────────┘ │
│                                            │
│  ⚠ This token expires in 1 hour            │
│                                            │
│  Configuration Command:                    │
│  ┌──────────────────────────────────────┐ │
│  │ ./config.sh \                      [📋]│ │
│  │   --url https://github.com/org \     │ │
│  │   --token AABBCCDD... \              │ │
│  │   --name worker-001 \                │ │
│  │   --labels linux,docker \            │ │
│  │   --ephemeral                        │ │
│  └──────────────────────────────────────┘ │
│                                            │
│  [View Runner]        [Done]               │
└────────────────────────────────────────────┘
```

---

## 5. Additional Features

### 5.1 Real-Time Updates

**WebSocket Integration:**
- Connection to backend via WebSocket for live updates
- Events: runner status change, new runner, runner deleted
- Toast notifications for important events

**Implementation:**
```typescript
// Pseudo-code
const ws = new WebSocket('wss://service.example.com/ws');

ws.on('runner.status_changed', (data) => {
  // Update React Query cache
  queryClient.setQueryData(['runners', data.id], data);
  // Show toast
  toast.info(`Runner ${data.name} is now ${data.status}`);
});
```

**Fallback:**
- Polling every 30 seconds if WebSocket not available
- Manual refresh button

### 5.2 Bulk Operations (Admin)

**Deprovision Multiple Runners:**
```
┌────────────────────────────────────────────┐
│  Deprovision 5 Runners?           [×]      │
├────────────────────────────────────────────┤
│  You are about to deprovision:             │
│                                            │
│  • runner-001 (alice@example.com)          │
│  • runner-002 (alice@example.com)          │
│  • runner-003 (bob@example.com)            │
│  • runner-004 (bob@example.com)            │
│  • runner-005 (carol@example.com)          │
│                                            │
│  ⚠ This action cannot be undone.           │
│                                            │
│  Type "DEPROVISION" to confirm:            │
│  [                                     ]   │
│                                            │
│  [Cancel]              [Deprovision]       │
└────────────────────────────────────────────┘
```

**Operations:**
- Deprovision all runners for a user
- Deprovision all offline runners
- Deprovision all runners with specific label

### 5.3 Export Functionality

**Export Options:**
```
┌────────────────────────────────┐
│  Export Runners       [×]      │
├────────────────────────────────┤
│  Format:                       │
│  ○ CSV                         │
│  ● JSON                        │
│  ○ Excel (XLSX)                │
│                                │
│  Include:                      │
│  ☑ Runner details              │
│  ☑ Labels                      │
│  ☑ Status                      │
│  ☑ Timestamps                  │
│                                │
│  Filters:                      │
│  ☑ Apply current filters       │
│                                │
│  [Cancel]      [Export]        │
└────────────────────────────────┘
```

### 5.4 Search

**Global Search (in nav bar):**
- Searches: runner names, labels, users
- Shows results grouped by type
- Quick navigation to detail pages

### 5.5 User Preferences

**Settings Page:**
```
┌────────────────────────────────────────────┐
│  Settings                                  │
├────────────────────────────────────────────┤
│  Profile                                   │
│  Name:    Alice Smith                      │
│  Email:   alice@example.com                │
│  Role:    Admin                            │
│                                            │
│  Preferences                               │
│  Theme:         ○ Light ● Dark ○ Auto     │
│  Timezone:      [UTC-8 (Pacific)      ▼]  │
│  Date Format:   [YYYY-MM-DD           ▼]  │
│  Items per page:[100                  ▼]  │
│                                            │
│  Notifications                             │
│  ☑ Email on security events                │
│  ☑ Browser notifications for status changes│
│  ☐ Weekly summary email                    │
│                                            │
│  [Save Changes]                            │
└────────────────────────────────────────────┘
```

### 5.6 System Health (Admin)

```
┌────────────────────────────────────────────┐
│  System Health                             │
├────────────────────────────────────────────┤
│  Service Status:  🟢 Healthy              │
│  Uptime:          99.98%                   │
│                                            │
│  Components:                               │
│  ┌──────────────────────────────────────┐ │
│  │ API Server        🟢 Healthy         │ │
│  │ Database          🟢 Healthy         │ │
│  │ GitHub API        🟢 Connected       │ │
│  │ OIDC Provider     🟢 Reachable       │ │
│  └──────────────────────────────────────┘ │
│                                            │
│  Metrics (Last 24h):                       │
│  API Requests:        12,450               │
│  Runners Provisioned: 87                   │
│  Avg Response Time:   145ms                │
│  Error Rate:          0.02%                │
│                                            │
│  [View Logs] [View Metrics]                │
└────────────────────────────────────────────┘
```

---

## 6. API Requirements (Backend Additions)

### 6.1 New Endpoints Needed

**Dashboard Statistics:**
```
GET /api/v1/dashboard/stats
Response:
{
  "total_runners": 42,
  "active_runners": 38,
  "offline_runners": 3,
  "pending_runners": 1,
  "runners_by_user": [
    {"user": "alice@example.com", "count": 12},
    {"user": "bob@example.com", "count": 8}
  ],
  "recent_activity": [
    {
      "timestamp": "2026-01-16T18:45:00Z",
      "event": "provision",
      "user": "alice@example.com",
      "runner": "runner-001"
    }
  ]
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

### 6.2 Enhanced Existing Endpoints

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

## 7. Security Considerations

### 7.1 Authentication & Authorization

**OIDC Token Management:**
- Store access token in memory (React state)
- Store refresh token in httpOnly cookie
- Implement token refresh logic
- Clear tokens on logout

**RBAC Enforcement:**
- Check admin role on frontend (UI hiding)
- **Critical:** Enforce on backend (API validation)
- Admin endpoints return 403 for non-admin users

**API Security:**
```typescript
// Axios interceptor
axios.interceptors.request.use((config) => {
  const token = authStore.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Token expired - try refresh
      await authService.refreshToken();
      // Retry original request
      return axios.request(error.config);
    }
    return Promise.reject(error);
  }
);
```

### 7.2 XSS Prevention

**Input Sanitization:**
- All user inputs sanitized with DOMPurify
- React's built-in XSS protection (no dangerouslySetInnerHTML)
- Content Security Policy headers

**CSP Header:**
```
Content-Security-Policy:
  default-src 'self';
  script-src 'self';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  connect-src 'self' wss://service.example.com;
```

### 7.3 CSRF Protection

**For SPA:**
- Not vulnerable to traditional CSRF (no cookies for auth)
- Use Bearer tokens in Authorization header
- Refresh token in httpOnly cookie with SameSite=Strict

### 7.4 Sensitive Data Handling

**Registration Tokens:**
- Display once in modal
- Mask in logs: `AAA...789` (first 3 + last 3 characters)
- Copy to clipboard with notification
- Clear from state after modal close

**Session Storage:**
- No sensitive data in localStorage
- Access token in memory only
- Refresh token in httpOnly cookie

---

## 8. Implementation Complexity Analysis

### 8.1 Token Estimation

**Component Development:**

| Component/Feature | Estimated Tokens | Complexity |
|-------------------|------------------|------------|
| Project Setup (Vite + React + TS) | 500 | Low |
| OIDC Authentication Integration | 2,000 | High |
| API Client (Axios + React Query) | 1,500 | Medium |
| Layout & Navigation | 1,500 | Low |
| Home Dashboard Page | 2,000 | Medium |
| Runners List Page | 3,000 | Medium |
| Runner Detail Page | 1,500 | Low |
| Provision Runner Modal | 1,500 | Low |
| Label Policies Page (Admin) | 2,500 | Medium |
| Security Events Page (Admin) | 2,000 | Medium |
| Audit Log Viewer | 1,500 | Low |
| Settings Page | 1,000 | Low |
| Admin Console | 2,000 | Medium |
| Bulk Operations | 1,500 | Medium |
| WebSocket Integration | 2,000 | High |
| Export Functionality | 1,000 | Low |
| Search Functionality | 1,500 | Medium |
| Responsive Design | 2,000 | Medium |
| Error Handling & Toasts | 1,000 | Low |
| Loading States | 1,000 | Low |
| Testing (Unit + E2E) | 3,000 | Medium |
| **Total (Frontend)** | **~32,000** | |

**Backend Additions:**

| Component | Estimated Tokens | Complexity |
|-----------|------------------|------------|
| Dashboard Stats Endpoint | 500 | Low |
| Admin Role Management | 1,000 | Medium |
| WebSocket Server | 2,000 | High |
| Bulk Operations API | 1,000 | Medium |
| Enhanced Query Parameters | 500 | Low |
| **Total (Backend)** | **~5,000** | |

**Documentation:**

| Document | Estimated Tokens | Complexity |
|----------|------------------|------------|
| API Documentation | 1,000 | Low |
| Deployment Guide | 1,000 | Low |
| User Manual | 1,500 | Low |
| **Total (Docs)** | **~3,500** | |

**Grand Total: ~40,500 tokens** (estimated for complete implementation)

### 8.2 Time Estimation

Assuming ~100-150 tokens = 1 hour of development:

- Frontend: ~200-250 hours (5-6 weeks full-time)
- Backend: ~30-40 hours (1 week full-time)
- Documentation: ~20-25 hours
- Testing & QA: ~40-50 hours
- **Total: ~300-365 hours (2-3 months full-time)**

---

## 9. Problematic Features & Blockers

### 9.1 Technical Challenges

**1. WebSocket Implementation**
- **Challenge:** Maintaining connections at scale, reconnection logic
- **Mitigation:** Use Socket.io for abstraction, fallback to polling
- **Blocker Level:** Medium
- **Alternative:** Polling-only (simpler but less real-time)

**2. OIDC Integration Complexity**
- **Challenge:** Different OIDC providers have subtle differences
- **Mitigation:** Use oidc-client-ts library (handles most providers)
- **Blocker Level:** Medium
- **Alternative:** Build provider-specific adapters

**3. Admin Role Management**
- **Challenge:** No existing admin role system in backend
- **Mitigation:** Add admin_users table or use OIDC claims
- **Blocker Level:** High (requires backend changes)
- **Alternative:** Maintain admin list in config file initially

**4. Real-Time Data Consistency**
- **Challenge:** Stale data with multiple users, cache invalidation
- **Mitigation:** React Query's refetch strategies, WebSocket events
- **Blocker Level:** Medium

**5. Large Dataset Pagination**
- **Challenge:** 1000+ runners, slow queries
- **Mitigation:** Backend pagination, cursor-based pagination
- **Blocker Level:** Low (backend handles)

### 9.2 Security Concerns

**1. Token Exposure in Browser**
- **Risk:** XSS can steal access token from memory
- **Mitigation:** Short-lived tokens (15 min), refresh mechanism
- **Severity:** Medium

**2. Admin Privilege Escalation**
- **Risk:** User modifies frontend to access admin features
- **Mitigation:** Backend MUST enforce RBAC on ALL endpoints
- **Severity:** Critical
- **Action Required:** Backend validation is mandatory

**3. WebSocket Message Authentication**
- **Risk:** Unauthorized clients receiving real-time updates
- **Mitigation:** Token validation on WebSocket handshake
- **Severity:** High

**4. Bulk Operation Abuse**
- **Risk:** Admin accidentally deprovisions all runners
- **Mitigation:** Confirmation dialogs, audit logging, rate limiting
- **Severity:** Medium

### 9.3 Deployment Blockers

**1. CORS Configuration**
- **Issue:** Frontend and backend on different origins
- **Solution:** Configure CORS in FastAPI
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashboard.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**2. OIDC Redirect URIs**
- **Issue:** OIDC provider must whitelist dashboard URLs
- **Solution:** Register https://dashboard.example.com/callback

**3. Static File Hosting**
- **Issue:** React SPA needs hosting
- **Options:**
  - Serve from FastAPI (simple, same origin)
  - CDN (better performance, requires CORS)
  - Reverse proxy (nginx)

---

## 10. Phased Implementation Plan

### Phase 1: MVP (Core Functionality)
**Timeline:** 4-6 weeks
**Features:**
- OIDC authentication
- Home dashboard (basic stats)
- Runners list (read-only)
- Runner detail view
- Provision runner flow
- Admin role check (basic)
- Responsive layout

**Token Estimate:** ~15,000 tokens

### Phase 2: Admin Features
**Timeline:** 3-4 weeks
**Features:**
- Label policies management
- Security events viewer
- Bulk operations
- Audit log viewer
- Admin console

**Token Estimate:** ~10,000 tokens

### Phase 3: Real-Time & Polish
**Timeline:** 2-3 weeks
**Features:**
- WebSocket integration
- Real-time status updates
- Toast notifications
- Search functionality
- Export functionality

**Token Estimate:** ~8,000 tokens

### Phase 4: Advanced Features
**Timeline:** 2-3 weeks
**Features:**
- User preferences
- System health monitoring
- Advanced filtering
- E2E testing

**Token Estimate:** ~7,000 tokens

---

## 11. Technology Alternatives

### 11.1 Framework Alternatives

**Option A: React (Recommended)**
- Pros: Large ecosystem, TanStack Query, mature
- Cons: Larger bundle size
- Use case: Best for complex, data-heavy dashboard

**Option B: Svelte**
- Pros: Smaller bundle, faster, simpler
- Cons: Smaller ecosystem
- Use case: If performance is critical

**Option C: Vue.js**
- Pros: Balance of simplicity and power
- Cons: Less TypeScript integration than React
- Use case: Team familiar with Vue

### 11.2 UI Library Alternatives

**Option A: shadcn/ui (Recommended)**
- Pros: Accessible, customizable, modern
- Cons: Requires Tailwind CSS

**Option B: Material UI**
- Pros: Complete, battle-tested
- Cons: Opinionated design, larger bundle

**Option C: Ant Design**
- Pros: Enterprise-ready, many components
- Cons: Less customizable, Asian-centric design

### 11.3 State Management Alternatives

**Option A: TanStack Query + Zustand (Recommended)**
- Server state: React Query (caching, refetching)
- Client state: Zustand (simple, fast)

**Option B: Redux Toolkit**
- Pros: One solution for everything
- Cons: More boilerplate, steeper learning curve

**Option C: Jotai/Recoil**
- Pros: Atomic state management
- Cons: Newer, smaller community

---

## 12. Deployment Architecture

```
┌───────────────────────────────────────────────────┐
│                  Users (Browser)                  │
└────────────────────┬──────────────────────────────┘
                     │ HTTPS
                     ▼
┌─────────────────────────────────────────────────────┐
│              Load Balancer / CDN                    │
│              (SSL Termination)                      │
└────────┬─────────────────────────────┬──────────────┘
         │                             │
         │ Static Assets               │ API Calls
         ▼                             ▼
┌────────────────────┐    ┌────────────────────────┐
│  Frontend (SPA)    │    │  Backend (FastAPI)     │
│  - React Bundle    │    │  - API Endpoints       │
│  - index.html      │    │  - WebSocket Server    │
│  - Static Files    │    │  - OIDC Validation     │
│                    │    │                        │
│  Hosted on:        │    │  Hosted on:            │
│  - S3 + CloudFront │    │  - Docker + K8s        │
│  - Vercel          │    │  - Cloud Run           │
│  - Nginx           │    │  - EC2/VM              │
└────────────────────┘    └───────┬────────────────┘
                                  │
                                  ▼
                          ┌────────────────┐
                          │   Database     │
                          │   (PostgreSQL) │
                          └────────────────┘
```

---

## 13. Accessibility Considerations

### 13.1 WCAG 2.1 AA Compliance

**Keyboard Navigation:**
- All interactive elements keyboard accessible
- Visible focus indicators
- Skip navigation link
- Logical tab order

**Screen Reader Support:**
- Semantic HTML (nav, main, aside, article)
- ARIA labels for icons
- ARIA live regions for dynamic updates
- Alt text for images

**Visual:**
- Color contrast ratio ≥ 4.5:1
- Text resizable to 200%
- No information by color alone
- Focus visible

**Implementation:**
- Use shadcn/ui (built on Radix UI - accessible by default)
- Test with axe DevTools
- Manual testing with NVDA/JAWS

---

## 14. Monitoring & Analytics

### 14.1 User Analytics

**Track:**
- Page views
- Feature usage (provision runner, deprovision, etc.)
- Error rates (by page)
- Average session duration

**Tools:**
- Plausible (privacy-focused, lightweight)
- Or: Self-hosted Matomo

### 14.2 Performance Monitoring

**Metrics:**
- Core Web Vitals (LCP, FID, CLS)
- API response times
- WebSocket connection stability

**Tools:**
- Sentry (error tracking)
- Web Vitals API
- Custom metrics to backend

---

## 15. Recommendations

### 15.1 Immediate Action Items

1. **Backend Priority:** Implement admin role system FIRST
   - Add `admin_users` table or use OIDC claims
   - Enforce RBAC on all admin endpoints

2. **MVP Scope:** Start with Phase 1 only
   - Prove value before building advanced features
   - Gather user feedback early

3. **Technology Decisions:**
   - Use React + TypeScript (recommended)
   - shadcn/ui for components
   - TanStack Query for server state
   - Deploy backend and frontend separately

4. **Security Focus:**
   - Backend RBAC is non-negotiable
   - Token management strategy before coding
   - Security review before Phase 2

### 15.2 Risk Mitigation

**High-Risk Items:**
1. Admin privilege escalation → Backend RBAC
2. WebSocket complexity → Start with polling, add WebSocket later
3. OIDC integration → Prototype early with test provider

**De-Risking Strategy:**
- Build authentication flow first (critical path)
- Create spike for WebSocket vs polling decision
- Test RBAC enforcement with automated tests

### 15.3 Success Metrics

**User Adoption:**
- 80% of users use dashboard instead of CLI
- <5 support tickets per week

**Performance:**
- Page load <2s
- API calls <500ms p95

**Security:**
- Zero privilege escalation incidents
- Zero XSS/CSRF vulnerabilities

---

## 16. Conclusion

The proposed dashboard is technically feasible with an estimated implementation effort of **~40,500 tokens (300-365 hours)**. The primary blocker is implementing backend RBAC for admin role enforcement, which is critical for security.

**Recommended Approach:**
1. Implement backend admin role system first (~5,000 tokens)
2. Build Phase 1 MVP (~15,000 tokens)
3. Validate with users
4. Iterate with Phase 2-4 based on feedback

**Key Success Factors:**
- Backend RBAC must be implemented before dashboard
- Start simple (polling) before complex (WebSocket)
- Security review at each phase
- User testing after MVP

The dashboard will significantly improve usability and provide administrators with powerful bulk management capabilities while maintaining the security boundaries established by the existing API.
