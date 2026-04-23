# Plan Mode Rules

See main [`AGENTS.md`](../../AGENTS.md) for general project rules.

## Architecture-Specific Considerations

### Monorepo Command Execution

Backend at root, frontend in `frontend/` subdirectory. This affects command execution:
- Backend commands: Run from root
- Frontend commands: Must run from `frontend/` directory
- Pre-commit hooks handle this via `bash -c 'cd frontend && npm run ...'`

### Circular Dependency Architecture

The codebase uses lazy imports inside functions to avoid circular dependencies. Models are imported inside functions, not at module level (except in TYPE_CHECKING blocks). This pattern is critical for the architecture. See [`app/auth/dependencies.py`](../../app/auth/dependencies.py:16-17) and [`app/services/label_policy_service.py`](../../app/services/label_policy_service.py:81).

### Database Architecture Modes

Two modes with different connection patterns:
- SQLite: Simple connection string, used for dev/test
- PostgreSQL with IAM auth: Uses creator function to generate fresh tokens per connection (15 min expiry), requires `db_pool_recycle` < 900s

See [`app/database.py`](../../app/database.py:17-80) for IAM token generation architecture.

### Test Environment Constraint

Tests require environment setup BEFORE any app imports because config validation happens on import. The [`tests/conftest.py`](../../tests/conftest.py:45-68) creates temp files and sets env vars before importing app modules. This is a critical architectural constraint.