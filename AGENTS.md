# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Test Environment Setup (Critical)

Tests require environment variables set BEFORE importing app modules. The [`tests/conftest.py`](tests/conftest.py:45-68) creates a temporary GitHub private key file and sets env vars before any app imports. If you add new config that's validated on import, update `_setup_test_environment()` first.

## Circular Dependency Prevention

Models are imported inside functions (not at module level) to avoid circular dependencies. Use `TYPE_CHECKING` for type hints:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models import User

def some_function():
    from app.models import User  # Actual import inside function
```
See [`app/auth/dependencies.py`](app/auth/dependencies.py:16-17) and [`app/services/label_policy_service.py`](app/services/label_policy_service.py:81).

## Database Configuration

- SQLite for dev/test (default): `sqlite:///./runner_service.db`
- PostgreSQL with IAM auth for AWS RDS: Set `db_iam_auth=true` and provide `db_host`, `db_name`, `db_username`, `aws_region`
- IAM tokens expire after 15 min; `db_pool_recycle` must be < 900s
- See [`app/database.py`](app/database.py:17-80) for IAM token generation

## Running Tests

**Backend (from root):**
```bash
pytest                                    # All tests
pytest tests/test_sync_worker.py         # Single file
pytest tests/test_sync_worker.py::test_worker_acquires_leadership  # Single test
pytest --cov=app --cov-report=html       # With coverage
```

**Frontend (must cd into frontend/):**
```bash
cd frontend
npm run test              # Watch mode
npm run test:run          # Single run
npm run test:coverage     # With coverage
```

## Container Tool

Makefile supports both podman and docker via `CONTAINER_TOOL` variable (default: podman):
```bash
make build                           # Uses podman
CONTAINER_TOOL=docker make build     # Uses docker
```

## Pre-commit Hooks

Pre-commit runs automatically on commit and includes:
- Ruff (Python linter/formatter)
- pytest (all backend tests)
- Frontend lint, typecheck, and tests
- Terraform fmt

Frontend hooks run FROM frontend/ directory via `bash -c 'cd frontend && npm run ...'`