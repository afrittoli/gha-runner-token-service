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

## Open

- [ ] P1, bug, Deletion of runners via API returns unauthorized, [details](#deletion-unauthorized)
- [ ] P2, feature, Implement user authorization table, [details](#user-authorization-table)
- [ ] P2, feature, Add coverage check workflow
- [ ] P3, feature, Design GitHub sync mechanism, [details](#github-sync)
- [ ] P3, test, Test label policy management
- [ ] P4, feature, Dashboard authentication and refresh button

---

## Details

### Deletion Unauthorized
Deletion of runners via API always returns unauthorized. Need to investigate if this is an identity mismatch issue - check if `provisioned_by` stored value matches current `user.identity`.

### User Authorization Table
OIDC should only be for authentication. Authorization should use an app-side user table.
- Create User model: id, email, display_name, oidc_sub, is_admin, is_active, created_at
- Add admin API endpoints for user CRUD
- Modify auth flow to check user exists in DB before allowing access
- Store display_name for dashboard (fixes "shows OIDC sub instead of email")
- Replace ADMIN_IDENTITIES env var with is_admin from User table

### GitHub Sync
Keep runner status in sync with GitHub. Options:
1. GitHub webhooks for runner events
2. Periodic polling job

---

## Rules

When implementing:
- **Bug fixes**: Must include a regression test
- **Features**: Must include new tests and document any untestable areas
