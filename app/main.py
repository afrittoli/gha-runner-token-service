"""Main FastAPI application."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.worker import SyncWorker

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import structlog

from app import __version__
from app.api.v1 import admin
from app.api.v1 import auth
from app.api.v1 import audit
from app.api.v1 import oauth_clients
from app.api.v1 import runners
from app.api.v1 import teams
from app.api.v1 import webhooks
from app.config import get_settings
from app.database import init_db, SessionLocal
from app.logging_config import setup_logging, log_access
from app.schemas import ErrorResponse, HealthResponse
from app.metrics import get_metrics

current_file_path = Path(__file__).parent.resolve()
favicon_path = current_file_path / "favicon.ico"

# Get settings
settings = get_settings()

# Setup logging with new configuration
setup_logging(
    log_level=settings.log_level,
    log_dir=settings.log_dir,
    access_log_tracing=settings.access_log_tracing,
)
logger = structlog.get_logger()


# Global sync worker reference
_sync_worker: Optional["SyncWorker"] = None
_sync_task: Optional[asyncio.Task] = None


def get_sync_status(db=None) -> dict:
    """
    Get current sync status for API.

    Reads from sync_state table in database, which is updated by the sync worker.
    This allows all API replicas to show consistent sync status.

    Args:
        db: Optional database session (for testing)
    """
    from app.models import SyncState

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        sync_state = db.query(SyncState).filter_by(id=1).first()

        if sync_state:
            last_sync_result = None
            if sync_state.last_sync_result:
                try:
                    last_sync_result = json.loads(sync_state.last_sync_result)
                except json.JSONDecodeError:
                    last_sync_result = {"error": "Invalid JSON in sync result"}

            return {
                "enabled": settings.sync_enabled,
                "interval_seconds": settings.sync_interval_seconds,
                "worker_hostname": sync_state.worker_hostname,
                "worker_heartbeat": sync_state.worker_heartbeat.isoformat()
                if sync_state.worker_heartbeat
                else None,
                "last_sync_time": sync_state.last_sync_time.isoformat()
                if sync_state.last_sync_time
                else None,
                "last_sync_result": last_sync_result,
                "last_sync_error": sync_state.last_sync_error,
            }
        else:
            # No sync state yet (worker hasn't started or using SQLite)
            return {
                "enabled": settings.sync_enabled,
                "interval_seconds": settings.sync_interval_seconds,
                "worker_hostname": None,
                "worker_heartbeat": None,
                "last_sync_time": None,
                "last_sync_result": None,
                "last_sync_error": "Sync worker not initialized (requires PostgreSQL)",
            }
    finally:
        if close_db:
            db.close()


# Create FastAPI app
app = FastAPI(
    title="GitHub Runner Token Service",
    description="Secure central service for managing GitHub self-hosted runner registrations",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware only when cross-origin access is needed.
# For same-origin deployments (frontend and API behind the same ingress host),
# leave CORS_ALLOWED_ORIGINS unset — no middleware is added and requests flow normally.
if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log HTTP requests with access logging."""
    start_time = time.time()

    try:
        response = await call_next(request)

        # Skip access logging for health checks to reduce noise
        if request.url.path == "/health":
            return response

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log access
        log_access(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            client=request.client.host if request.client else None,
            headers=dict(request.headers),
            duration_ms=duration_ms,
        )

        return response

    except Exception as e:
        # Log the failure
        duration_ms = (time.time() - start_time) * 1000
        logger.exception(
            "request_failed",
            method=request.method,
            path=request.url.path,
            error=str(e),
            duration_ms=duration_ms,
        )
        raise


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.warning("validation_error", path=request.url.path, errors=exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            detail="Validation error", error_code="VALIDATION_ERROR"
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            detail="Internal server error", error_code="INTERNAL_ERROR"
        ).model_dump(),
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    global _sync_worker, _sync_task

    logger.info(
        "application_starting", version=__version__, github_org=settings.github_org
    )

    # Initialize database
    try:
        init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.exception("database_initialization_failed", error=str(e))
        raise

    # Start sync worker with leader election if enabled
    if settings.sync_enabled:
        from app.worker import SyncWorker

        _sync_worker = SyncWorker()
        _sync_task = asyncio.create_task(_sync_worker.start())
        logger.info(
            "sync_worker_started",
            leader_election_enabled=True,
            note="Only one pod will become sync leader via PostgreSQL advisory lock",
        )


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _sync_worker, _sync_task

    logger.info("application_shutting_down")

    # Request graceful shutdown of sync worker
    if _sync_worker is not None:
        _sync_worker.request_shutdown()
        logger.info("sync_worker_shutdown_requested")

    # Cancel sync task if running
    if _sync_task is not None:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass
        logger.info("sync_worker_stopped")


# Health check endpoint (no auth required)
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint.

    Returns service status and version information.
    No authentication required.
    """
    return HealthResponse(
        status="healthy", version=__version__, timestamp=datetime.now(timezone.utc)
    )


@app.get("/metrics", tags=["System"], include_in_schema=False)
async def metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    No authentication required for monitoring.
    """
    metrics_data, content_type = get_metrics()
    return Response(content=metrics_data, media_type=content_type)


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "service": "GitHub Runner Token Service",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(favicon_path)


app.include_router(runners.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(teams.router, prefix="/api/v1/admin")
app.include_router(oauth_clients.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")

# Note: Frontend is now served separately by Nginx in Kubernetes deployment
# For local development, run the frontend with: cd frontend && npm run dev


if __name__ == "__main__":
    import uvicorn

    # Build uvicorn config
    uvicorn_config = {
        "app": "app.main:app",
        "host": settings.service_host,
        "port": settings.service_port,
        "reload": True,
        "log_level": settings.log_level.lower(),
        "access_log": True,  # Enable uvicorn's access logs on console
    }

    # Add HTTPS configuration if enabled
    if settings.https_enabled:
        if not settings.https_cert_file or not settings.https_key_file:
            logger.error(
                "https_config_error",
                message="HTTPS enabled but cert_file or key_file not configured",
            )
            raise ValueError(
                "HTTPS_CERT_FILE and HTTPS_KEY_FILE are required when HTTPS_ENABLED=true"
            )

        uvicorn_config["ssl_certfile"] = str(settings.https_cert_file)
        uvicorn_config["ssl_keyfile"] = str(settings.https_key_file)
        logger.info(
            "https_enabled",
            cert_file=str(settings.https_cert_file),
            key_file=str(settings.https_key_file),
        )

    uvicorn.run(**uvicorn_config)
