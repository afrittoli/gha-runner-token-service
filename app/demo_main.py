"""
Demo entry point — NOT for production use.

This module extends the production app with impersonation endpoints and
impersonation-token auth support. It is only present in demo container images;
the production Dockerfile never copies it or app/demo/.

Usage (demo image CMD):
    uvicorn app.demo_main:app --host 0.0.0.0 --port 8000
"""

import structlog

# Import demo models before app.main so they register with Base.metadata
# and are included when init_db() calls Base.metadata.create_all().
import app.demo.models as _demo_models  # noqa: F401

from app.main import app
from app.auth import dependencies as _prod_auth
from app.demo.auth import get_current_user as _demo_get_current_user
from app.demo.router import router as _demo_router

logger = structlog.get_logger()

logger.warning(
    "demo_mode_active",
    message=(
        "DEMO MODE: impersonation endpoints enabled. "
        "This build must NOT be used in production."
    ),
)

# Override the auth dependency so all routes transparently support
# impersonation tokens without any change to production code.
app.dependency_overrides[_prod_auth.get_current_user] = _demo_get_current_user

app.include_router(_demo_router, prefix="/api/v1")
