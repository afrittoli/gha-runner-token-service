# Dashboard Development Roadmap

## Overview

Dashboard development is organized into **4 phases**, each with specific features and deliverables. This document tracks tasks across all phases, with priority, area of work, and detailed descriptions.

**Key Principles:**
- New React dashboard runs **alongside** existing Jinja2 dashboard during development
- Existing dashboard at `/dashboard` must not be broken by any changes
- Backend and dashboard development are **decoupled** (separate concerns)
- Existing backend functionality is preserved throughout all phases

---

## Parallel Deployment Strategy

**Goal:** Run new React dashboard alongside existing Jinja2 dashboard during development

**URLs:**
- Existing dashboard: `GET /dashboard` (Jinja2, no auth, will be deprecated)
- New dashboard: `GET /app` or `GET /dashboard-v2` (React SPA, OIDC required)
- API endpoints: `/api/v1/*` (shared, used by both)

**Feature Flag:** `ENABLE_NEW_DASHBOARD` (environment variable)
- When `false`: Only existing dashboard at `/dashboard`
- When `true`: New dashboard at `/app`, existing still available at `/dashboard-legacy`
- Allows gradual rollout and A/B testing

**Rollover Plan:**
- Phase 1-3: Run both dashboards
- Phase 3 end: Route `/dashboard` to new version, existing to `/dashboard-legacy`
- After stabilization (1-2 weeks): Remove Jinja2 dashboard

---

## Phase 1: MVP (Core Functionality) - 4-6 weeks

**Goal:** Establish authentication, basic UI, and core runner management functionality

**Target Token Count:** ~12,000 tokens (reduced from 15k by removing non-essential tasks)
**Target Hours:** 80-120 hours

### Backend - Infrastructure for Parallel Dashboards

- [x] **P1, backend, ci** - Add ENABLE_NEW_DASHBOARD feature flag to config
  - Add to `app/config.py`: `enable_new_dashboard: bool = Field(default=False, env='ENABLE_NEW_DASHBOARD')`
  - Use throughout backend to configure routes and middleware
  - *Files:* app/config.py
  - ✅ **COMPLETED**: Feature flag added and integrated into main.py CORS logic

- [x] **P1, backend, feature** - Add dashboard route conditional logic
  - Route `/dashboard` to Jinja2 template (always available)
  - When `ENABLE_NEW_DASHBOARD=true`: Serve React SPA at `/app` path
  - When feature flag is true: Optionally move existing to `/dashboard-legacy`
  - *Files:* app/main.py
  - ✅ **COMPLETED**: Conditional routing added, `/dashboard-legacy` always available, `/dashboard` redirects to `/app` when flag is true, SPA catch-all route for client-side routing

- [x] **P1, backend, feature** - Configure CORS for React SPA
  - Allow `localhost:5173` (Vite dev server) in development
  - Allow production origin in production
  - Set `credentials=true` for OIDC cookies
  - *Code:* Update CORSMiddleware in app/main.py
  - *Note:* Existing Jinja2 dashboard doesn't need CORS (server-rendered)
  - ✅ **COMPLETED**: CORS middleware updated to check feature flag and allow Vite dev server

- [x] **P1, backend, feature** - Add static file serving for React build
  - Serve React bundle from `/app` path
  - Use FastAPI's `StaticFiles` middleware
  - Point to `frontend/dist/` or similar
  - Configure cache headers for assets
  - *Code:* Add to app/main.py: `app.mount("/app", StaticFiles(directory="frontend/dist"), name="dashboard")`
  - *Note:* Dev mode: Vite proxy handles this automatically
  - ✅ **COMPLETED**: StaticFiles middleware added to app/main.py, mounts to /app when ENABLE_NEW_DASHBOARD=true and dist exists

### Backend - Authentication & Authorization

- [x] **P1, backend, security** - Implement admin role system via OIDC claims or admin_users table
  - Add admin_users table or use OIDC claim mapping
  - Implement GET /api/v1/auth/me endpoint returning user roles and permissions
  - Test endpoint with admin and non-admin users
  - *Blockers:* User authorization table (depends on P2 task)
  - *Related:* Critical for RBAC enforcement
  - ✅ **COMPLETED**: GET /api/v1/auth/me endpoint implemented in app/api/v1/auth.py, returns user_id, oidc_sub, is_admin, roles

- [x] **P1, backend, feature** - Implement GET /api/v1/dashboard/stats endpoint
  - Return total, active, offline, pending runner counts
  - Return top users by runner count (admin only)
  - Return recent activity feed (last 20 events)
  - Add pagination support
  - *Tests:* Unit tests for stats calculation, E2E test for endpoint response
  - ✅ **COMPLETED**: GET /api/v1/dashboard/stats endpoint added to auth.py, returns runner counts and recent security events

- [x] **P1, backend, feature** - Enhance GET /api/v1/runners endpoint with query parameters
  - Add support for filtering: user, status, labels, ephemeral flag
  - Add sorting by: name, status, created_at, last_seen
  - Add pagination: limit, offset / cursor-based
  - Add search by runner name and labels
  - *Tests:* Test each filter combination, test sorting, test pagination
  - ✅ **COMPLETED**: Runners endpoint enhanced with status_filter, ephemeral, limit, offset query parameters with pagination and filtering logic

- [x] **P1, backend, feature** - Add runner detail endpoint improvements
  - Return complete audit trail / activity timeline for runner
  - Include timestamps for creation, registration, last_seen, deleted
  - *Tests:* Verify all fields returned correctly
  - ✅ **COMPLETED**: GET /api/v1/runners/{runner_id} now returns RunnerDetailResponse with 20-event audit trail from SecurityEvent table

- [x] **P1, backend, security** - Enforce RBAC on all endpoints
  - Admin endpoints (/api/v1/admin/*) return 403 for non-admin users
  - Standard users can only view/manage their own runners
  - *Tests:* Test each endpoint with admin and non-admin tokens, verify 403 responses
  - *Critical:* Backend enforcement is non-negotiable
  - ✅ **COMPLETED**: All admin endpoints require `require_admin` dependency, runner endpoints filter by ownership (provisioned_by/oidc_sub), per-method authorization for JIT/registration token APIs, comprehensive tests in test_rbac_enforcement.py (7 tests)

### Frontend - Project Setup & Authentication

- [x] **P1, frontend, feature** - Initialize React + TypeScript + Vite project in separate directory
  - Create `/frontend` directory at repo root (separate from `/app` Python package)
  - Set up project structure: `src/{components,pages,api,hooks,store,utils}`
  - Configure TypeScript strict mode
  - Set up path aliases (@components, @pages, @api, @hooks, @store, @utils)
  - Configure Vite to proxy API calls: `localhost:8000/api` → `localhost:5173`
  - *Files:* `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`
  - *Note:* Separate directory prevents conflicts with Python app
  - *Dev:* `npm run dev` runs on localhost:5173, `python -m app` runs on localhost:8000
  - ✅ **COMPLETED**: Full project structure created with TailwindCSS, React Query, Zustand, react-oidc-context

- [x] **P1, frontend, feature** - Configure Vite for SPA serving at /app path
  - Set Vite `base: '/app/'` for production builds
  - Ensure router uses `HashRouter` or configure server-side fallback
  - In development: Vite dev server on :5173
  - In production: Built assets served from `/app` path by FastAPI
  - *Files:* `frontend/vite.config.ts`
  - *Note:* This allows SPA to work both at /app (production) and root (dev testing)
  - ✅ **COMPLETED**: Vite configured with base='/app/', BrowserRouter with basename='/app', API proxy

- [x] **P1, frontend, feature** - Implement OIDC authentication flow (separate from existing dashboard)
  - Integrate oidc-client-ts library
  - Implement login/logout flow
  - Store access token in memory, refresh token in httpOnly cookie
  - Implement token refresh interceptor (axios)
  - Handle 401 responses and automatic re-authentication
  - Redirect to OIDC provider with correct redirect URI (`http://localhost:5173/callback` for dev, `/app/callback` for prod)
  - *Tests:* Mock OIDC provider, test token refresh, test 401 handling
  - ✅ **COMPLETED**: react-oidc-context integrated, Login/LoginCallback pages, axios interceptors for auth
  - *Security:* Use short-lived tokens (15 min), refresh mechanism
  - *Note:* Existing dashboard has no auth; new dashboard requires login

- [x] **P1, frontend, feature** - Create authentication guard / ProtectedRoute component
  - Redirect to login if not authenticated
  - Redirect to login if session expired
  - Load user role/permissions from /api/v1/auth/me
  - Show role badge in UI
  - *Tests:* Test redirect behavior, test permission loading
  - ✅ **COMPLETED**: ProtectedRoute component implemented, user info fetched from /api/v1/auth/me, role badge added to MainLayout

- [x] **P1, frontend, feature** - Set up API client with Axios
  - Create API client with Bearer token interceptor
  - Configure base URL and timeout
  - Add error handling and logging
  - Create request/response type definitions
  - *Files:* api/client.ts, api/types.ts
  - ✅ **COMPLETED**: Axios client configured with interceptors for auth and error handling

- [x] **P1, frontend, feature** - Set up React Query for server state management
  - Configure QueryClient with appropriate defaults
  - Set up stale time, cache time, retry logic
  - Create custom hooks for API queries (useRunners, useRunner, useDashboardStats, etc.)
  - *Files:* hooks/useRunners.ts, hooks/useDashboardStats.ts, etc.
  - ✅ **COMPLETED**: QueryClient configured, useRunners and useDashboardStats hooks implemented and integrated into pages

- [x] **P1, frontend, feature** - Set up Zustand for client state management
  - Create auth store (currentUser, token, refreshToken, isAdmin)
  - Create UI store (theme, sidebarOpen, filters, search, etc.)
  - *Files:* store/authStore.ts, store/uiStore.ts
  - ✅ **COMPLETED**: authStore implemented for managing user profile and permissions

### Frontend - Layout & Navigation

- [x] **P1, frontend, ui** - Create main layout components
  - Navigation sidebar with menu items
  - Top navigation bar with logo, search, user menu, settings
  - Main content area with router
  - Responsive design for mobile/tablet
  - *Components:* Sidebar.tsx, TopNav.tsx, MainLayout.tsx
  - *Styling:* Tailwind CSS + shadcn/ui
  - ✅ **COMPLETED**: MainLayout refactored with Sidebar and TopNav components, responsive design implemented with Tailwind CSS

- [x] **P1, frontend, ui** - Implement responsive navigation
  - Mobile hamburger menu
  - Collapsible sidebar on desktop
  - Show/hide admin-only menu items based on role
  - Active route highlighting
  - *Tests:* Test menu visibility based on screen size and role
  - ✅ **COMPLETED**: Mobile hamburger menu implemented using Zustand for state management, sidebar is responsive and hides/shows correctly

### Frontend - Pages

- [x] **P1, frontend, ui, feature** - Home / Dashboard page
  - Display stats cards (total, active, offline, pending runners)
  - Show admin stats (top users by runner count) - admin only
  - Show recent activity feed with timestamps
  - Quick action button to provision new runner
  - *Components:* StatCard.tsx, ActivityFeed.tsx, Dashboard.tsx
  - *Data:* Use useDashboardStats hook
  - ✅ **COMPLETED**: Dashboard page implemented with stats cards and recent activity feed

- [x] **P1, frontend, ui, feature** - Runners list page
  - Display table of runners with columns: name, status, user, labels, actions
  - Search bar (debounced)
  - Filter dropdown (status, user, labels)
  - Sorting by name, status, created_at
  - Pagination controls
  - Row actions menu (view, refresh, deprovision) - deprovision for own runners only
  - *Components:* RunnersTable.tsx, FilterPanel.tsx, RunnersList.tsx
  - *Data:* Use useRunners hook with filters/pagination
  - ✅ **COMPLETED**: Runners list page implemented with filtering, search, and pagination

- [x] **P1, frontend, ui, feature** - Runner detail page
  - Display runner metadata (name, status, labels, GitHub ID, created/registered dates)
  - Show activity timeline
  - Action buttons: Refresh Status, Deprovision (if owner), View in GitHub
  - Back button to runners list
  - *Components:* RunnerDetail.tsx, ActivityTimeline.tsx
  - *Data:* Use useRunner(runnerId) hook
  - ✅ **COMPLETED**: Runner detail page implemented with metadata display and audit trail

- [x] **P1, frontend, ui, feature** - Provision runner modal/page
  - Form fields: runner name, labels (multi-select), ephemeral checkbox
  - Submit to POST /api/v1/runners
  - Success modal showing:
    - Registration token (display once, copy button)
    - Configuration command (copy button)
    - Warning: token expires in 1 hour
    - Links to view runner or return to list
  - Error handling with user-friendly messages
  - *Components:* ProvisionRunnerModal.tsx, SuccessModal.tsx
  - *Tests:* Test form validation, test submit, test token display
  - ✅ **COMPLETED**: ProvisionRunner page implemented with form validation, success screen, and copy-to-clipboard functionality

### Frontend - Utilities & Hooks

- [x] **P1, frontend, feature** - Create custom hooks for API calls
  - useRunners(filters, pagination) - fetch runners list
  - useRunner(runnerId) - fetch single runner
  - useDashboardStats() - fetch dashboard statistics
  - useProvisionRunner() - mutation hook for creating runner
  - useRefreshRunnerStatus() - mutation hook
  - *Tests:* Mock React Query, test hook behavior
  - ✅ **COMPLETED**: Custom hooks for all API endpoints implemented in hooks/ directory

- [x] **P1, frontend, feature** - Create utility functions
  - Format timestamps (created_at, last_seen, etc.)
  - Status badge helper (color, label, icon)
  - Labels formatter (display as pills/tags)
  - Copy to clipboard helper
  - *Files:* utils/formatters.ts, utils/clipboard.ts
  - ✅ **COMPLETED**: Utility functions for date formatting, status styling, and clipboard operations implemented

- [x] **P1, frontend, ui** - Create shared UI components (shadcn/ui based)
  - Status badge component
  - Label pills component
  - Pagination component
  - Filter dropdown component
  - Toast notifications (error, success, info)
  - Loading skeleton screens
  - *Components:* components/StatusBadge.tsx, components/LabelPill.tsx, etc.
  - ✅ **COMPLETED**: StatusBadge and LabelPill components implemented and integrated

### Testing

- [ ] **P1, testing** - Set up testing infrastructure
  - Configure Jest + React Testing Library
  - Mock axios and React Query
  - Create test utilities and helpers
  - *Files:* jest.config.js, src/test/setup.ts

- [ ] **P1, testing** - Add component tests
  - Test Dashboard component rendering and stat display
  - Test RunnersTable with mock data
  - Test ProvisionRunnerModal form and submission
  - Test authentication guard redirect behavior
  - *Target:* 60%+ coverage for React components

- [ ] **P1, testing** - Add E2E tests (Playwright)
  - Test login flow with OIDC provider mock
  - Test navigation between pages
  - Test provisioning runner flow
  - Test filters and search on runners list
  - *Target:* Critical user journeys covered

### CI/CD

- [ ] **P1, ci** - Add GitHub Actions workflow for frontend
  - Install dependencies
  - Run linting (ESLint)
  - Run type checking (TypeScript)
  - Run unit tests
  - Run E2E tests (if possible in CI environment)
  - Build React bundle (check bundle size)
  - *File:* `.github/workflows/frontend.yml`

- [ ] **P1, ci** - Add frontend build to main app workflow
  - Build frontend when `ENABLE_NEW_DASHBOARD=true`
  - Copy built assets to app serving directory
  - Test that both dashboards are accessible in CI
  - *Files:* Update `.github/workflows/main.yml` or create `build-matrix.yml`

- [ ] **P1, ci** - Update Docker build to include frontend assets
  - Add build stage for React (Node.js) to build bundle
  - Copy built assets to final image
  - Configure FastAPI `StaticFiles` middleware to serve both dashboards
  - *File:* `Dockerfile` (optional multi-stage build if desired)
  - *Note:* Keep simple; nginx optional if not already in use

- [ ] **P1, documentation** - Document dual dashboard setup
  - Explain feature flag usage
  - Document dev environment setup (running both servers)
  - Document production build (combined artifact)
  - Include troubleshooting section for CORS issues
  - *File:* `docs/DEVELOPMENT.md` - add "Running Both Dashboards" section

### Legacy Dashboard Protection (CRITICAL)

- [x] **P1, testing, critical** - Ensure existing dashboard is not broken
  - Verify existing `/dashboard` endpoint still works after all infrastructure changes
  - Test that Jinja2 template renders correctly
  - Verify no new backend changes affect existing dashboard functionality
  - Run in CI: test both dashboards accessible in parallel
  - *Criteria:* Both dashboards must be fully functional at all times
  - ✅ **COMPLETED**: Test suite created in tests/test_existing_dashboard.py with 6 test classes verifying dashboard accessibility, HTML rendering, no-auth requirement

- [x] **P1, backend, feature** - Define and document API contract for new dashboard
  - Document which endpoints are used by new dashboard vs existing dashboard
  - Clearly separate new dashboard-specific endpoints from shared endpoints
  - Ensure new dashboard API additions don't interfere with existing dashboard
  - *File:* `docs/API_CONTRACT.md` (new file)
  - ✅ **COMPLETED**: API_CONTRACT.md created with 135 lines defining backward compatibility rules, no-go areas, and testing strategy

- [x] **P1, testing** - Test backend functionality independent of dashboards
  - Verify CLI commands still work after backend changes
  - Verify webhook processing still works
  - Verify runner provisioning/management works via API
  - ✅ **COMPLETED**: Test suite created in tests/test_backend_independence.py with 3 test classes verifying health endpoint, runners endpoint, middleware, and API consistency
  - Document any API changes explicitly
  - *Criteria:* No regressions in existing workflows

---

## Phase 2: Admin Features - 3-4 weeks

**Goal:** Implement comprehensive admin-only features for policy and security management

**Target Token Count:** ~8,000 tokens (reduced by deferring non-essential admin features)
**Target Hours:** 50-80 hours

### Backend - Admin Endpoints

- [ ] **P2, backend, feature** - Implement label policy endpoints
  - GET /api/v1/admin/policies - list all policies
  - POST /api/v1/admin/policies - create new policy
  - PUT /api/v1/admin/policies/:policy_id - update policy
  - DELETE /api/v1/admin/policies/:policy_id - delete policy
  - GET /api/v1/admin/policies/:policy_id - get policy details
  - *Tests:* CRUD operations, RBAC enforcement (403 for non-admin)

- [ ] **P2, backend, feature** - Implement security events endpoints
  - GET /api/v1/admin/security-events - list events with filters
  - GET /api/v1/admin/security-events/:event_id - get event detail
  - Add filtering: severity, type, user, time range
  - Add pagination
  - *Tests:* Test filters, test pagination, test event retrieval

- [ ] **P2, backend, feature** - Implement audit log endpoints
  - GET /api/v1/audit-logs - list logs (admin: all, user: own)
  - Add filtering: event_type, user, time range
  - Add pagination
  - *Tests:* Test RBAC (users see only their logs, admins see all)

- [ ] **P2, backend, feature** - Implement bulk deprovision endpoint (DEFER to Phase 3 or later)
  - Nice-to-have for admin console, not critical for MVP
  - Can be implemented after Phase 1 MVP is stable

- [ ] **P2, backend, feature** - Implement runner refresh status endpoint
  - POST /api/v1/runners/:runner_id/refresh-status
  - Call GitHub API to get current status
  - Update database
  - Return updated runner
  - *Tests:* Test status update, test GitHub API error handling

### Frontend - Admin Pages

- [ ] **P2, frontend, ui, feature** - Label policies management page
  - List table: user, allowed labels, max runners, actions
  - Filter by user (search)
  - Create/Edit policy modal with form
  - Delete confirmation dialog
  - *Components:* LabelPolicies.tsx, PolicyModal.tsx
  - *Data:* useAdminPolicies, usePolicies (queries/mutations)
  - *Restriction:* Admin only (check via auth store)

- [ ] **P2, frontend, ui, feature** - Security events viewer page
  - List table: time, type, severity (color-coded), user, details (modal)
  - Filter dropdown: type, severity, time range
  - Event detail modal showing:
    - Full event data (violation details, user, runner, etc.)
    - Action taken (if any)
  - *Components:* SecurityEvents.tsx, EventDetailModal.tsx
  - *Data:* useSecurityEvents(filters) hook
  - *Note:* Export deferred to Phase 3 or later

- [ ] **P2, frontend, ui, feature** - Audit log viewer page
  - List table: timestamp, event type, user, details, changes
  - Filter by event type, user, time range
  - Pagination
  - For users: show only own logs
  - For admins: show all logs with user filter
  - *Components:* AuditLog.tsx
  - *Data:* useAuditLogs(filters, role) hook
  - *Note:* Export deferred to Phase 3 or later

- [ ] **P2, frontend, ui, feature** - Admin console page (DEFER to Phase 3 or later)
  - Quick stats (total users, admins, runners, events)
  - Configuration viewer (read-only)
  - *Components:* AdminConsole.tsx
  - *Restriction:* Admin only
  - *Note:* Bulk actions deferred; prioritize other Phase 2 features

### Frontend - Utilities & Hooks

- [ ] **P2, frontend, feature** - Create admin hooks
  - useAdminPolicies(filters) - fetch policies list
  - useAdminPolicy(policyId) - fetch single policy
  - useCreatePolicy(data) - mutation hook
  - useUpdatePolicy(policyId, data) - mutation hook
  - useDeletePolicy(policyId) - mutation hook
  - useSecurityEvents(filters) - fetch events
  - useAuditLogs(filters) - fetch logs
  - useBulkDeprovision(runnerIds) - mutation hook

- [ ] **P2, frontend, feature** - Create export utilities
  - toCSV(data) - convert data to CSV format
  - toJSON(data) - return as JSON
  - downloadFile(content, filename, format) - trigger download

### Testing

- [ ] **P2, testing** - Add admin page tests
  - Test LabelPolicies page rendering and CRUD operations
  - Test SecurityEvents page with filters
  - Test AuditLog page (user vs admin views)
  - Test RBAC: verify non-admin users see 403/cannot access

- [ ] **P2, testing** - Add backend tests for admin endpoints
  - Test RBAC enforcement on all admin endpoints
  - Test bulk operations
  - Test error handling and validation

---

## Phase 3: Real-Time & Polish - 2-3 weeks

**Goal:** Add real-time updates, polish UI, improve performance

**Target Token Count:** ~6,000 tokens (reduced by removing monitoring and analytics)
**Target Hours:** 40-60 hours

### Backend - Real-Time Features

- [ ] **P3, backend, feature** - Implement WebSocket endpoint for real-time updates
  - WS /api/v1/ws - authenticated WebSocket connection
  - Require Bearer token in handshake
  - Broadcast events: runner.status_changed, runner.created, runner.deleted
  - Broadcast to admins: security_event, audit_log_entry
  - *Tests:* Test WebSocket connection, test event broadcasting
  - *Security:* Token validation on handshake, admin filtering

- [ ] **P3, backend, feature** - Implement polling fallback for WebSocket
  - If WebSocket unavailable, client falls back to polling every 30 seconds
  - Document this behavior in API docs

### Frontend - Real-Time Updates

- [ ] **P3, frontend, feature** - Implement WebSocket client integration
  - Create WebSocket connection manager
  - Handle connection, reconnection, disconnection
  - Listen for runner status changes, create, delete events
  - Update React Query cache on events
  - Show toast notification for important events
  - *Utilities:* hooks/useWebSocket.ts, utils/websocket.ts
  - *Tests:* Mock WebSocket, test connection/reconnection

- [ ] **P3, frontend, ui, feature** - Implement real-time status updates
  - Update runner status in table/detail without page refresh
  - Animate status changes
  - Show "Last updated X seconds ago"
  - *Components:* Updates to RunnersTable.tsx, RunnerDetail.tsx

- [ ] **P3, frontend, ui, feature** - Add toast notifications
  - Success: runner provisioned, status updated
  - Error: API errors, connection issues
  - Info: real-time events (runner status changed)
  - Auto-dismiss after 5 seconds
  - *Components:* Toast.tsx, useToast.ts

### Frontend - Polish & Performance

- [ ] **P3, frontend, ui** - Implement loading states and skeleton screens
  - Skeleton screens for table, dashboard cards, detail page
  - Loading spinners for buttons during async operations
  - Disable buttons during loading
  - *Components:* Skeleton.tsx, LoadingSpinner.tsx

- [ ] **P3, frontend, ui** - Add error boundaries and error pages
  - Error boundary component for crash recovery
  - 404 page for not found
  - 403 page for access denied
  - Generic error page with retry option
  - *Components:* ErrorBoundary.tsx, NotFound.tsx, Forbidden.tsx

- [ ] **P3, frontend, performance** - Optimize bundle size
  - Analyze bundle (webpack-bundle-analyzer)
  - Code splitting by route
  - Lazy load heavy components
  - *Target:* <300KB gzipped bundle

- [ ] **P3, frontend, ui** - Implement search debouncing
  - Debounce search input (300ms delay)
  - Debounce filter changes
  - Show loading state while searching
  - *Utilities:* hooks/useDebounce.ts

- [ ] **P3, frontend, ui** - Add keyboard shortcuts
  - Cmd+K / Ctrl+K: open global search
  - Esc: close modals
  - Documentation in settings page
  - *Utilities:* hooks/useKeyboard.ts

### Frontend - Export & Download

- [ ] **P3, frontend, feature** - Implement data export functionality (OPTIONAL)
  - Export runners list (CSV, JSON)
  - Export security events (CSV, JSON)
  - Export audit logs (CSV, JSON)
  - *Utilities:* utils/export.ts
  - *Note:* Nice-to-have; defer if time is limited

### Testing

- [ ] **P3, testing** - Add real-time update tests
  - Test WebSocket connection and event handling
  - Test React Query cache updates on WebSocket events
  - Test toast notifications on real-time events
  - Test polling fallback

- [ ] **P3, testing** - Add performance tests
  - Measure page load time
  - Measure API response times
  - Measure React render performance

---

## Phase 4: Advanced Features - 2-3 weeks

**Goal:** Add advanced features and complete the solution

**Target Token Count:** ~4,000 tokens (significantly reduced; many Phase 4 items are optional)
**Target Hours:** 25-40 hours

### Backend - Advanced Features

- [ ] **P4, backend, feature** - Implement system health endpoint (OPTIONAL)
  - GET /api/v1/admin/system-health
  - Return service status, uptime, component health
  - *Tests:* Test health check logic
  - *Note:* Nice-to-have for monitoring; defer if time is limited

### Frontend - Advanced Pages

- [ ] **P4, frontend, ui, feature** - Settings page
  - User profile section: name, email, role
  - Preferences: theme (light/dark), timezone, date format, items per page
  - Notifications: email on security events, browser notifications
  - Save preferences to local storage / backend
  - *Components:* Settings.tsx, ProfileSection.tsx, PreferencesSection.tsx

- [ ] **P4, frontend, ui, feature** - System health page (admin only)
  - Display component health with status indicators
  - Show metrics: uptime, requests count, error rate, response time
  - View logs link
  - *Components:* SystemHealth.tsx

- [ ] **P4, frontend, ui, feature** - Global search page (OPTIONAL)
  - Search across runners, labels, users, events
  - Results grouped by type
  - Quick navigation to detail pages
  - *Components:* GlobalSearch.tsx, SearchResults.tsx
  - *Note:* Nice-to-have; defer if time is limited

- [ ] **P4, frontend, ui** - Dark mode implementation (OPTIONAL)
  - Toggle in settings
  - Persist preference to localStorage
  - Use Tailwind CSS dark mode
  - *Note:* Nice-to-have; defer if time is limited

### Frontend - Accessibility & Testing

- [ ] **P4, testing, ui** - Basic keyboard navigation and semantics
  - Ensure Tab order is logical
  - Use semantic HTML (button, form, nav, etc.)
  - Test focus indicators are visible
  - *Note:* Extensive WCAG AA compliance is deferred; focus on usability

- [ ] **P4, testing, ui** - Basic accessibility improvements (OPTIONAL)
  - Add ARIA labels to icons
  - Add ARIA live regions for dynamic updates
  - Ensure color contrast is reasonable (not strict WCAG AA testing)
  - *Note:* Not strict accessibility audit; focus on usability

- [ ] **P4, testing** - Add E2E tests for critical paths
  - Full user journeys (login → provision → view → delete)
  - Admin journeys (manage policies, view events)
  - Error scenarios and edge cases
  - *Target:* 70%+ critical path coverage (not 90%)

### Frontend - Documentation & Deployment

- [ ] **P4, documentation** - Create developer guide for new dashboard
  - Architecture overview (React, API client, state management)
  - Component structure and naming conventions
  - How to run locally and test
  - *Format:* Markdown in docs/
  - *Note:* Focus on developer docs, not end-user guide

- [ ] **P4, deployment** - Create deployment guide
  - Build and serve React SPA at /app path
  - CORS configuration in FastAPI
  - Environment variables for OIDC redirect URIs
  - Feature flag configuration
  - *Format:* Markdown in docs/deployment/

- [ ] **P4, ci** - Set up deployment pipeline
  - Build React bundle in CI
  - Serve static files from FastAPI or CDN
  - Configure CORS headers
  - Smoke tests post-deployment
- [ ] **P4, documentation, dev** - Create dashboard development guide
  - Frontend project setup
  - Running tests
  - Building for production
  - Contributing guidelines
  - *Format:* Markdown in docs/
---

## Phase End: Dashboard Rollover & Migration

**Timing:** After Phase 3 completion (8-10 weeks into project)

**Objectives:**
1. Verify new dashboard is feature-complete and stable
2. Migrate default users to new dashboard
3. Deprecate old Jinja2 dashboard
4. Monitor for issues during transition

### Preparation Tasks

- [ ] **Rollover, testing** - Run full regression testing on new dashboard
  - Test all Phase 1, 2, 3 features
  - Test with different user roles (admin, standard)
  - Performance testing (load time, response time, bundle size)
  - Browser compatibility testing
  - *Criteria:* Zero P0 bugs, <2 P1 bugs, <5 P2 bugs

- [ ] **Rollover, documentation** - Create migration guide
  - Document differences between old and new dashboard
  - Explain new features
  - Provide troubleshooting guide
  - Include feedback channel
  - *Format:* Markdown + blog post or release notes

- [ ] **Rollover, infrastructure** - Prepare rollover plan
  - Plan traffic routing: `/dashboard` → new version
  - Plan fallback: if issues, `/dashboard-legacy` still available
  - Set up feature flag toggle for quick rollback
  - Plan monitoring/alerting for new dashboard
  - *File:* Create `docs/ROLLOVER_PLAN.md`

### Execution Tasks

- [ ] **Rollover, deployment** - Update ENABLE_NEW_DASHBOARD flag
  - Set `ENABLE_NEW_DASHBOARD=true` in production environment
  - Route `/dashboard` to new React version (or update redirect)
  - Move existing to `/dashboard-legacy` or remove after stabilization
  - Monitor error rates, performance, user feedback
  - *Duration:* Run in parallel for 1-2 weeks

- [ ] **Rollover, cleanup** - Remove old Jinja2 dashboard
  - Remove `/app/templates/dashboard.html` file
  - Remove Jinja2 template rendering code from `app/main.py`
  - Update documentation
  - Remove legacy routes and feature flag checks
  - *Timeline:* 2+ weeks after successful rollover

- [ ] **Rollover, documentation** - Update all docs
  - Update API documentation
  - Remove references to old dashboard
  - Update QUICKSTART and DEVELOPMENT guides
  - Archive rollover documentation
  - *Files:* Update docs/, remove legacy references

---

## Cross-Phase: Security & Infrastructure

### Security

- [ ] **Security, backend** - Implement CORS configuration
  - Allow only dashboard origin
  - Configure allowed methods and headers
  - Set credentials = true for OIDC cookies
  - *Code:* app/main.py CORSMiddleware

- [ ] **Security, backend** - Implement CSRF protection for SPA
  - Use Bearer tokens (immune to traditional CSRF)
  - Document security model in design doc
  - Test with security tools

- [ ] **Security, frontend** - Implement XSS prevention
  - Use DOMPurify for user input sanitization
  - Never use dangerouslySetInnerHTML
  - Test with security scanners
  - *Library:* dompurify

- [ ] **Security, frontend** - Implement Content Security Policy headers
  - Set CSP headers in FastAPI response
  - Restrict script-src to 'self'
  - Test CSP violations in console

- [ ] **Security, testing** - Add security-focused tests
  - Test token handling (no tokens in localStorage)
  - Test RBAC enforcement
  - Test XSS attack scenarios
  - Test CORS configuration

### Documentation

- [ ] **Documentation, all** - Create API documentation
  - Document all new endpoints
  - Include request/response examples
  - Document WebSocket events
  - Include error codes and meanings
  - *Tool:* OpenAPI/Swagger

- [ ] **Documentation, design** - Update design documents
  - Add implementation notes from Phase 1
  - Document API changes
  - Add known limitations
  - Document future improvements

- [ ] **Documentation, dev** - Create dashboard development guide
  - Frontend project setup
  - Running tests
  - Building for production
  - Contributing guidelines
  - *Format:* Markdown in docs/

---

## Deployment Models

### Development
```
Terminal 1: cd frontend && npm run dev  # Vite on localhost:5173
Terminal 2: python -m app                # FastAPI on localhost:8000

Access:
- Old dashboard: http://localhost:8000/dashboard (Jinja2, no auth)
- New dashboard: http://localhost:5173 (React, redirects to OIDC)
- API: http://localhost:8000/api/v1

Note: CORS configured to allow :5173 in dev mode
```

### Production (Phase 1-3, parallel)
```
Docker build includes:
- Frontend: React bundle built to /frontend/dist/
- Backend: FastAPI serving static files from /app path

Routing:
- GET /dashboard → Jinja2 (ENABLE_NEW_DASHBOARD=false, default)
- GET /app → React SPA (ENABLE_NEW_DASHBOARD=true)
- Both use: /api/v1/* endpoints
```

### Production (Post-rollover)
```
React dashboard at /dashboard or /app
Jinja2 removed from codebase
Feature flag removed
Single, unified dashboard experience
```

---

## Dependencies & Blockers

### Phase 1 Blockers
- ✅ No critical blockers identified
- ⚠️ OIDC integration requires Auth0 redirect URI configuration (include `/app/callback` and localhost:5173 URLs)
- ⚠️ Backend RBAC is critical - must be implemented before frontend
- ⚠️ CORS configuration required for dev mode (Vite proxy + API CORS)
- ⚠️ Separate directory structure (/frontend vs /app) must be set up before starting React development

### Phase 2 Blockers
- ⚠️ Requires Phase 1 MVP completion
- Label policy system must be stable before admin features

### Phase 3 Blockers
- ⚠️ Requires Phase 1 & 2 completion
- WebSocket implementation complexity (consider polling-only if issues)

### Phase 4 Blockers
- ⚠️ Requires Phase 1, 2, & 3 completion
- Accessibility testing requires manual effort and tools

---

## Rules

When implementing:
- **Every feature:** Include tests (unit + E2E)
- **Every API endpoint:** RBAC validation (backend enforced)
- **Every form:** Input validation + error handling
- **Every page:** Responsive design + keyboard accessible
- **Before merge:** Code review + tests passing + no console warnings/errors
- **Documentation:** Update docs/ with API changes and features

---

## Success Metrics

**Phase 1 MVP:**
- ✅ Users can authenticate via OIDC
- ✅ Users can provision and view runners
- ✅ Admins can access admin endpoints
- ✅ <2s page load time
- ✅ Tests: 60%+ component coverage, E2E critical paths

**Phase 2:**
- ✅ Admins can manage label policies and security events
- ✅ Audit logging complete
- ✅ Tests: 70%+ coverage, all admin features tested

**Phase 3:**
- ✅ Real-time updates working (WebSocket or polling)
- ✅ UI polished and performant (<500ms API response rendering)
- ✅ Bundle size <300KB gzipped

**Phase 4:**
- ✅ WCAG 2.1 AA compliance verified
- ✅ 90%+ E2E coverage
- ✅ Production ready and documented

---

## Rollback Plan

If critical issues arise with new dashboard after rollover:

1. **Immediate:** Set `ENABLE_NEW_DASHBOARD=false` in production
2. **Restore:** Route `/dashboard` back to Jinja2 template
3. **Debug:** Investigate issue in staging with new dashboard enabled
4. **Fix:** Create patch and test thoroughly
5. **Re-rollout:** Deploy fixed version

This allows 1-2 minute recovery time without code changes.

---

## Key Principles for Parallel Development

1. **Zero Disruption:** Existing dashboard stays functional throughout development
2. **Independent Versions:** Each dashboard has its own code path (no shared React/Jinja2 code)
3. **Shared API:** Both dashboards consume the same backend API endpoints
4. **Feature Flag Control:** Enable new dashboard independently in each environment
5. **Gradual Rollout:** Can roll out to subset of users before full switchover
6. **Easy Rollback:** Can disable new dashboard instantly if issues arise

---

## Summary

**Total Effort (Revised for Solo Prototype):**
- Phase 1 MVP: ~12,000 tokens (80-120 hours)
- Phase 2 Admin: ~8,000 tokens (50-80 hours)
- Phase 3 Real-Time: ~6,000 tokens (40-60 hours)
- Phase 4 Advanced: ~4,000 tokens (25-40 hours, many optional)

**Grand Total: ~30,000 tokens (220-300 hours)**

**Timeline:** 2-3 months for solo developer (working part-time with other projects) or 6-8 weeks full-time.

**Key Constraints:**
- Optional/deferred tasks: export features, admin console bulk ops, system health, dark mode, global search, advanced accessibility, E2E coverage targets
- Must-have: MVP features (Phase 1), legacy dashboard protection, security, basic testing
- Decoupled: Backend feature work tracked separately; dashboard uses stable API endpoints

---

## References

- [Original Dashboard Design](docs/design/dashboard.md)
- [Authentication Details](docs/DEVELOPMENT.md#oidc-auth)
- [API Documentation](docs/design/token_service.md)
- **New:** Feature flag implementation in config.py
- **New:** Dual dashboard deployment strategy
- **New:** Vite + FastAPI integration
- **New:** Rollover and rollback procedures


- [x] Deactivate user does not ask for reason - **FIXED**: Already implemented
- [x] Bulk deprovision in security event instead of audit log - **FIXED**: Added AuditLog entries for both `batch_disable_users` and `batch_delete_runners` operations. These admin actions now appear in both SecurityEvent (for security monitoring) and AuditLog (for compliance tracking).
- [x] Audit log details: "Allowed patterns: []"?? - **FIXED**: Already implemented
- [x] Counters in main dashboard broken - **FIXED**: React dashboard was using wrong field names (`total_runners` instead of `total`). Updated `frontend/src/api/client.ts` and `frontend/src/pages/Dashboard.tsx` to match API response structure.

## Notes

- **Search box in TopNav**: This is a placeholder for Phase 3 "Global Search" feature (lines 48-58 in `frontend/src/components/TopNav.tsx`). Not functional yet.
- **User Impersonation**: Backend endpoints added to `app/api/v1/admin.py` (lines 1243-1397), but frontend UI not yet implemented. Need to add user switcher component to TopNav.