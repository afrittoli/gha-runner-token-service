# Ask Mode Rules

See main [`AGENTS.md`](../../AGENTS.md) for general project rules.

## Additional Context for Documentation

### Test Organization

Tests use SQLite in-memory by default. The naming convention is historical:
- Files named `test_*_service.py` → Unit tests (mock external dependencies)
- Files named `test_*.py` (most) → Integration tests (use test database)
- Files named `test_*_flow.py` or `test_*_provisioning.py` → E2E tests

See [`tests/README_TESTS.md`](../../tests/README_TESTS.md:38-54) for details.

### Monorepo Structure

Backend at root, frontend in `frontend/` subdirectory. Commands must be run from appropriate directories:
- Backend: Run from root (`pytest`, `python -m app.cli`)
- Frontend: Run from `frontend/` (`npm run test`, `npm run lint`)