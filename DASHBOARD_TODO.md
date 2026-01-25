# Dashboard Development Roadmap

## Overview

Dashboard development is organized into **4 phases**, each with specific features and deliverables. This document tracks tasks across all phases, with priority, area of work, and detailed descriptions.

**Key Principles:**
- New React dashboard is the primary dashboard
- Backend and dashboard development are **decoupled** (separate concerns)
- Existing backend functionality is preserved throughout all phases

---

## Open Tasks

### High Priority

- [ ] **Remove legacy Jinja2 dashboard** - Clean up all docs, backend, frontend, tests, and TODOs related to old dashboard
  - Remove `app/templates/dashboard.html`
  - Remove Jinja2 template rendering code from `app/main.py`
  - Remove `ENABLE_NEW_DASHBOARD` feature flag from config
  - Remove `/dashboard-legacy` route
  - Update all documentation references
  - Remove legacy dashboard tests (`tests/test_existing_dashboard.py`)
  - Update `docs/API_CONTRACT.md` to remove legacy references
  - Clean up DASHBOARD_TODO.md sections about parallel deployment

### Phase 1: MVP - Remaining Items

#### CI/CD
- [ ] **P1, ci** - Update Docker build to include frontend assets
- [ ] **P1, documentation** - Document dashboard setup

#### Testing
- [ ] **P1, testing** - Add E2E tests (Playwright) - Deferred to Phase 3

### Phase 2: Admin Features - Remaining Items

#### Frontend
- [ ] **P2, frontend, feature** - Create export utilities

### Phase 3: Real-Time & Polish - 2-3 weeks

#### Backend
- [ ] **P3, backend, feature** - Implement WebSocket endpoint
- [ ] **P3, backend, feature** - Implement polling fallback

#### Frontend
- [ ] **P3, frontend, feature** - Implement WebSocket client
- [ ] **P3, frontend, ui, feature** - Real-time status updates
- [ ] **P3, frontend, ui, feature** - Add toast notifications
- [ ] **P3, frontend, ui** - Loading states and skeleton screens
- [ ] **P3, frontend, ui** - Error boundaries and error pages
- [ ] **P3, frontend, performance** - Optimize bundle size
- [ ] **P3, frontend, ui** - Implement search debouncing
- [ ] **P3, frontend, ui** - Add keyboard shortcuts
- [ ] **P3, frontend, feature** - Data export functionality (OPTIONAL)

#### Testing
- [ ] **P3, testing** - Add real-time update tests
- [ ] **P3, testing** - Add performance tests

### Phase 4: Advanced Features - 2-3 weeks

#### Backend
- [ ] **P4, backend, feature** - System health endpoint (OPTIONAL)

#### Frontend
- [ ] **P4, frontend, ui, feature** - Settings page
- [ ] **P4, frontend, ui, feature** - System health page (admin)
- [ ] **P4, frontend, ui, feature** - Global search page (OPTIONAL)
- [ ] **P4, frontend, ui** - Dark mode (OPTIONAL)

#### Testing & Accessibility
- [ ] **P4, testing, ui** - Basic keyboard navigation
- [ ] **P4, testing, ui** - Basic accessibility improvements (OPTIONAL)
- [ ] **P4, testing** - E2E tests for critical paths

#### Documentation & Deployment
- [ ] **P4, documentation** - Create developer guide
- [ ] **P4, deployment** - Create deployment guide
- [ ] **P4, ci** - Set up deployment pipeline
- [ ] **P4, documentation, dev** - Dashboard development guide

### Cross-Phase: Security & Infrastructure

#### Security
- [ ] **Security, backend** - Implement CORS configuration
- [ ] **Security, backend** - Implement CSRF protection
- [ ] **Security, frontend** - Implement XSS prevention
- [ ] **Security, frontend** - Content Security Policy headers
- [ ] **Security, testing** - Security-focused tests

#### Documentation
- [ ] **Documentation, all** - Create API documentation
- [ ] **Documentation, design** - Update design documents
- [ ] **Documentation, dev** - Dashboard development guide

---

## Completed Tasks

### Phase 1: MVP - Completed

#### Backend Infrastructure
- [x] ENABLE_NEW_DASHBOARD feature flag
- [x] Dashboard route conditional logic
- [x] CORS for React SPA
- [x] Static file serving for React
- [x] GitHub Actions workflow for frontend
- [x] Frontend build in main workflow

#### Backend Auth & Authorization
- [x] Admin role system implementation
- [x] GET /api/v1/dashboard/stats endpoint
- [x] Enhanced GET /api/v1/runners endpoint
- [x] Runner detail endpoint improvements
- [x] RBAC enforcement on all endpoints

#### Frontend Setup
- [x] React + TypeScript + Vite project
- [x] Vite SPA serving at /app
- [x] OIDC authentication flow
- [x] Authentication guard / ProtectedRoute
- [x] API client with Axios
- [x] React Query for server state
- [x] Zustand for client state

#### Frontend Layout & Navigation
- [x] Main layout components
- [x] Responsive navigation

#### Frontend Pages
- [x] Home / Dashboard page
- [x] Runners list page
- [x] Runner detail page
- [x] Provision runner modal/page

#### Frontend Utilities & Hooks
- [x] Custom hooks for API calls
- [x] Utility functions (formatters, clipboard)
- [x] Shared UI components (badges, pills)

#### Testing
- [x] Testing infrastructure (Vitest setup)
- [x] Component tests (41 tests, 100% pass)
- [x] Legacy dashboard protection tests
- [x] API contract documentation
- [x] Backend independence tests

### Phase 2: Admin Features - Completed

#### Backend
- [x] Label policy endpoints
- [x] Security events endpoints
- [x] Audit log endpoints
- [x] Bulk deprovision endpoint
- [x] Runner refresh status endpoint

#### Frontend Admin Pages
- [x] Label policies management (12 tests)
- [x] Security events viewer (14 tests)
- [x] Audit log viewer (15 tests)
- [x] Admin console page

#### Frontend Utilities
- [x] Admin hooks (useAdmin.ts)

#### Testing
- [x] Admin page tests (41 total)
- [x] Backend tests for admin endpoints

---

## Deployment Model

### Development
```
Terminal 1: cd frontend && npm run dev  # Vite on localhost:5173
Terminal 2: python -m app                # FastAPI on localhost:8000

Access:
- Dashboard: http://localhost:5173 (React, redirects to OIDC)
- API: http://localhost:8000/api/v1

Note: CORS configured to allow :5173 in dev mode
```

### Production
```
Docker build includes:
- Frontend: React bundle built to /frontend/dist/
- Backend: FastAPI serving static files from /app path

Routing:
- GET /dashboard or /app → React SPA (OIDC required)
- API: /api/v1/* endpoints
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

## Summary

**Total Effort (Revised for Solo Prototype):**
- Phase 1 MVP: ~12,000 tokens (80-120 hours) ✅ COMPLETE
- Phase 2 Admin: ~8,000 tokens (50-80 hours) ✅ COMPLETE
- Phase 3 Real-Time: ~6,000 tokens (40-60 hours)
- Phase 4 Advanced: ~4,000 tokens (25-40 hours, many optional)

**Grand Total: ~30,000 tokens (220-300 hours)**

**Timeline:** 2-3 months for solo developer (working part-time with other projects) or 6-8 weeks full-time.

**Key Constraints:**
- Optional/deferred tasks: export features, system health, dark mode, global search, advanced accessibility, E2E coverage targets
- Must-have: MVP features (Phase 1), security, basic testing
- Decoupled: Backend feature work tracked separately; dashboard uses stable API endpoints

---

## References

- [Original Dashboard Design](docs/design/dashboard.md)
- [Authentication Details](docs/DEVELOPMENT.md#oidc-auth)
- [API Documentation](docs/design/token_service.md)
- **New:** Feature flag implementation in config.py
- **New:** Vite + FastAPI integration

---

## Fixed Issues

- [x] Deactivate user does not ask for reason
- [x] Bulk deprovision in security event instead of audit log
- [x] Audit log details: "Allowed patterns: []"??
- [x] Counters in main dashboard broken

---

## Notes

- **Search box in TopNav**: Placeholder for Phase 3 "Global Search" feature (lines 48-58 in `frontend/src/components/TopNav.tsx`). Not functional yet.
- **User Impersonation**: Backend endpoints added to `app/api/v1/admin.py` (lines 1243-1397), but frontend UI not yet implemented. Need to add user switcher component to TopNav.