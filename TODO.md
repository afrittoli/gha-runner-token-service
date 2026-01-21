# Open TODOs and Known Issues

## Completed
- [x] (Claude) DEVELOPMENT.md: get user credentials from the M2M auth0 application
- [x] (Claude) DEVELOPMENT.md: Env variable names are the same for different accounts which leads to confusion
- [x] (Claude) Add a linter workflow to the repo that uses a self-hosted runner
- [x] Test E2E provisioning with runner removal after job has been run
- [x] Test adding, listing, removing runners with different users
- [x] (Claude) Implement basic dashboard
- [x] (Claude) Refactor API to use runner_id instead of runner_name
- [x] (Claude) Runners remain in pending state until sync - fixed via documentation
- [x] (Claude) Runners do not pick up queued jobs - fixed via org settings docs
- [x] (Claude) Streamline docs, remove duplicates
- [x] (Claude) Fix delete runner returns 500 instead of 404 for wrong user
- [x] (Claude) Review updated docs (Haiku changes)
- [x] (Claude) Trim dashboard design doc
- [x] (Claude) Implement admin role checking via ADMIN_IDENTITIES env var
- [x] (Claude) Catch up on missing tests (55 tests added)
- [x] (Claude) Add unit test workflow
- [x] (Claude) Add precommit configuration for linting and unit tests
- [x] (Claude) Design and implement GitHub sync mechanism (65 tests total)
- [x] (Claude) Add JIT based service as alternative to registration token (85 tests total)
- [x] (Claude) Fix JIT runners missing self-hosted label (86 tests total)
- [x] (Claude) Fix deletion via API returns unauthorized - identity mismatch (87 tests total)
- [x] (Claude) Rework docs to prioritize JIT, add Podman examples, clarify sync is automatic
- [x] (Claude) Fix HTTPS_ENABLED docs - clarified that `python -m app.main` is required, or use uvicorn SSL flags directly
- [x] (Claude) Add periodic sync logging - logs `periodic_sync_triggered` and `periodic_sync_completed` events
- [x] (Claude) Add coverage check workflow - 55% threshold, codecov token support
- [x] (Claude) Add label policy tests - system label detection, edge cases (89 tests total)
- [x] (Claude) Implement user authorization table with per-method API access control (139 tests total)
- [x] (Claude) Cherry-pick dashboard branch work: feature flag, CORS, API contract, auth endpoint, static files, runner detail (178 tests total)
- [x] (Claude) Add batch admin endpoints with audit trail: disable users, delete runners (189 tests total)
- [x] (Claude) Add Admin Actions UI to dashboard: disable users, delete runners with comment requirement (189 tests total)

## Open
- [ ] P4, feature, Dashboard authentication and refresh button
- [ ] P5, feature, Dashboard next phase, based on the design
- [ ] P3, docs, convert SVG diagram into draw.io format
- [ ] P3, docs, read from docs/DEMO.md, check its feasibility, identify missing features and complement with commands for the demo
 

---

## Details

### User Authorization Table
OIDC should only be for authentication. Authorization should use an app-side user table.
- Create User model: id, email, display_name, oidc_sub, is_admin, is_active, created_at
- Add admin API endpoints for user CRUD
- Modify auth flow to check user exists in DB before allowing access
- Store display_name for dashboard (fixes "shows OIDC sub instead of email")
- Replace ADMIN_IDENTITIES env var with is_admin from User table
- Allow admin to configure which API can be used by which user. Can use something like regex based or functionality based (reg token vs jit)

### JIT
GitHub exposes an [API for JIT](https://docs.github.com/en/rest/actions/self-hosted-runners?apiVersion=2022-11-28#create-configuration-for-a-just-in-time-runner-for-an-organization). Instead of returning a registration token, the runner-token-service should validate the requested labels and if compliant return a JIT in the response. Things required:
- Create a design document. Update other design documents
- Add a JIT based provisioning API. All tests and docs needs to be updated accordingly.
- If possible, enforce ephemeral mode
- Update the sync service to detect deviations of labels between registration and sync time
    - If a runner has different labels and is idle, write to audit log and delete it
    - if a runner has different labels and is running a job, write to audit log. If enabled in config, delete it too.
- Switch to HTTPs (configurable), enhance the development docs to specify how to disable HTTPs in dev environments or setup self-signed certificates


---

## Rules

When implementing:
- **Bug fixes**: Must include a regression test
- **Features**: Must include new tests and document any untestable areas
