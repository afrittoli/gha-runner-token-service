# Service Demo Script

Demonstrate the system capabilities and its security and central management and auditing benefits.

## Clean-up

Users pre-provisioned. Label policies defined. No runners.

## Demonstrate Setup

- Use the dashboard to show existing users and no runners
- Use the dashboard to show label policies

## Provision a Runner

- User obtains token from OIDC service
- Attempts to provision a runner (JIT) with invalid labels, rejected
- Show audit log
- Provision a runner with valid labels, success.
- Show the runner in the dashboard
- Explain how "self-hosted" and OS/ARCH labels are managed
- Show the content of JIT
- Start the runner
- Show the runner in GitHub UI
- Show the runner in the dashboard. Explain the out of band sync.

## Demo Label Change Prevention

- Is it possible to use creds in the JIT to alter labels?
- If so, show how, and show how the sync system detects that and deletes the runner
- Provision a second runner for the same user if the previous one was deleted

## Demo Multi-User

- Provision a runner for a new user and start it
- Show runners in admin dashboard
- Show runners for Alice and Bob via API
- Bob tries to delete Alice's runner, failed
- Bob tries to delete his runner, success
- Bob provisions a new runner, trying to use Alice's runner number, failed
- Bob steals Alice's JIT, tries to use it, failed (can only be used once)
- Explain how group_id control in JIT could also be used to keep workflow separated
- Bob provisions a new runner, success

## Demo Ephemeral Runners

- Run a workflow (via manual trigger) to pick up a Job
- Show how the runner is deleted afterwards
- Show audit log (API, dashboard)

## Demo Admin Capabilites

- Provision a few runners (not started) for Bob and Alice
- Alter the label policy for a user
- Add a new user
- Disable a user (to be implemented)
- Disable all users, restore users
- Delete a runner
- Delete all runners for an user
- Delete all runners
- Show audit trail. Dashboard/API requires explanation on admin actions (to be implemented, shown in the log)