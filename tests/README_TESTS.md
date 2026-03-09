# Test Suite Documentation

## Overview

This directory contains the test suite for GHARTS (GitHub Actions Runner Token Service). Tests are organized by functionality and use pytest as the test framework.

## Test Categories

### Unit Tests

Tests that verify individual components in isolation with mocked dependencies:

- `test_label_policy_service.py` - Label policy validation logic
- `test_runner_service.py` - Runner provisioning logic
- `test_sync_worker.py` - Sync worker leader election and lifecycle

### Integration Tests

Tests that verify interactions between components with real database:

- `test_api.py` - Basic API endpoint functionality
- `test_auth_endpoint.py` - Authentication flows
- `test_runners.py` - Runner CRUD operations
- `test_admin.py` - Admin API endpoints
- `test_oauth_clients.py` - OAuth client management
- `test_teams.py` - Team management
- `test_audit.py` - Audit logging
- `test_webhooks.py` - GitHub webhook handling

### End-to-End Tests

Tests that verify complete workflows with minimal mocking:

- `test_jit_provisioning.py` - Just-in-time runner provisioning flow
- `test_rbac_enforcement.py` - Role-based access control
- `test_backend_independence.py` - Frontend/backend separation

## Test Naming Convention

The current test suite uses the term "integration tests" for tests that are actually unit tests with database fixtures. This is a historical naming convention.

**Actual Test Types:**
- Files named `test_*_service.py` → Unit tests (mock external dependencies)
- Files named `test_*.py` (most) → Integration tests (use test database)
- Files named `test_*_flow.py` or `test_*_provisioning.py` → E2E tests

**Future Improvement:**
Consider renaming or reorganizing tests into subdirectories:
```
tests/
  unit/          # Pure unit tests with mocks
  integration/   # Tests with real database
  e2e/          # End-to-end workflow tests
```

## Running Tests

### All Tests
```bash
pytest
```

### Specific Test File
```bash
pytest tests/test_sync_worker.py
```

### Specific Test Function
```bash
pytest tests/test_sync_worker.py::test_worker_acquires_leadership
```

### With Coverage
```bash
pytest --cov=app --cov-report=html
```

### Verbose Output
```bash
pytest -v
```

## Test Fixtures

Common fixtures are defined in `conftest.py`:

- `test_db` - SQLite in-memory database session
- `client` - FastAPI test client
- `admin_user` - Admin user for testing
- `regular_user` - Regular user for testing
- `admin_auth_override` - Bypass auth for admin tests
- `user_auth_override` - Bypass auth for user tests

## Test Database

Tests use SQLite in-memory database by default for speed. Some tests may require PostgreSQL-specific features (like advisory locks) and should be marked accordingly:

```python
@pytest.mark.postgresql
def test_advisory_locks():
    # Test that requires PostgreSQL
    pass
```

## Mocking Guidelines

### External Services

Always mock external services:
- GitHub API calls (`httpx` requests)
- OIDC provider calls
- Email sending
- External webhooks

### Database

Use real database (SQLite in-memory) for most tests. Only mock database for:
- Testing error handling
- Testing connection failures
- Performance-critical unit tests

### Time

Use `freezegun` or manual time mocking for time-dependent tests:

```python
from unittest.mock import patch
from datetime import datetime, timezone

with patch('app.services.sync_service.datetime') as mock_dt:
    mock_dt.now.return_value = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Test time-dependent logic
```

## Known Issues

### Fragile Timeout Tests

Some tests use `asyncio.wait_for(..., timeout=1.0)` which may fail on slow CI systems. If tests fail intermittently with `TimeoutError`, consider:
- Increasing timeout values
- Using event-based synchronization instead of timeouts
- Marking tests as `@pytest.mark.slow`

### Database Session Management

Tests should use `test_db.commit()` to persist changes, not `test_db.close()`. The `test_db` fixture manages session lifecycle.

## Contributing

When adding new tests:

1. Use descriptive test names: `test_<what>_<when>_<expected>`
2. Add docstrings explaining what the test verifies
3. Use appropriate fixtures from `conftest.py`
4. Mock external dependencies
5. Clean up resources in test teardown
6. Add test to appropriate category (unit/integration/e2e)

## CI/CD

Tests run automatically on:
- Pull requests
- Pushes to main branch
- Nightly builds

CI configuration: `.github/workflows/test.yml`