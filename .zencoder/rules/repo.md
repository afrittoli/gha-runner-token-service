---
description: Repository Information Overview
alwaysApply: true
---

# Repository Information Overview

## Repository Summary
A secure central service for managing GitHub self-hosted runner registrations with OIDC authentication. It acts as a secure intermediary between third parties and GitHub's registration API, providing JIT provisioning, label policy enforcement, and comprehensive audit trails.

## Repository Structure
The repository is organized as a multi-project setup with a Python backend and a React-based frontend dashboard.

### Main Repository Components
- **Backend (`app/`)**: FastAPI application providing the core logic for GitHub App integration, OIDC authentication, and runner management.
- **Frontend (`frontend/`)**: React dashboard built with Vite for administrative visibility and runner management.
- **Tests (`tests/`)**: Comprehensive test suite for the backend services and API endpoints.
- **Docs (`docs/`)**: Extensive documentation covering design, development, OIDC setup, and usage examples.

## Projects

### Backend Service (FastAPI)
**Configuration File**: `requirements.txt`, `app/config.py`

#### Language & Runtime
**Language**: Python  
**Version**: 3.11+ (tested on 3.13 in CI)  
**Build System**: pip  
**Package Manager**: pip

#### Dependencies
**Main Dependencies**:
- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `sqlalchemy`: ORM for database management
- `PyJWT` & `python-jose`: JWT and OIDC handling
- `httpx`: Async HTTP client for GitHub API
- `pydantic`: Data validation and settings management
- `structlog`: Structured logging

**Development Dependencies**:
- `pytest`, `pytest-asyncio`, `pytest-cov`: Testing framework
- `ruff`: Linting and formatting
- `httpx`: Test client

#### Build & Installation
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Initialize database
python -m app.cli init-db
```

#### Docker
**Dockerfile**: `Dockerfile`
**Image**: `python:3.11-slim`
**Configuration**:
- Exposes port 8000.
- Uses `uvicorn` to run the FastAPI app.
- Supports volume mounting for database and private keys.
- `docker-compose.yml` provides a complete local environment setup.

#### Testing
**Framework**: pytest
**Test Location**: `tests/`
**Naming Convention**: `test_*.py`
**Configuration**: `pytest.ini`, `tests/conftest.py`

**Run Command**:
```bash
pytest
# With coverage
pytest --cov=app --cov-report=term-missing
```

### Frontend Dashboard (React)
**Configuration File**: `frontend/package.json`

#### Language & Runtime
**Language**: TypeScript  
**Version**: Node.js (LTS recommended)  
**Build System**: Vite  
**Package Manager**: npm

#### Dependencies
**Main Dependencies**:
- `react`: UI library
- `@tanstack/react-query`: Data fetching and caching
- `zustand`: State management
- `react-router-dom`: Routing
- `axios`: HTTP client
- `react-oidc-context`: OIDC authentication integration
- `tailwindcss`: Styling

**Development Dependencies**:
- `vite`: Build tool
- `typescript`: Type checking
- `eslint`: Linting

#### Build & Installation
```bash
cd frontend
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

#### Testing
**Framework**: ESLint, TypeScript (Static analysis)
**Configuration**: `frontend/.eslintrc.cjs`, `frontend/tsconfig.json`

**Run Command**:
```bash
cd frontend
npm run lint
npm run typecheck
```
