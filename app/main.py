"""Main FastAPI application."""

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import structlog

from app import __version__
from app.api.v1 import admin
from app.api.v1 import auth
from app.api.v1 import audit
from app.api.v1 import runners
from app.api.v1 import teams
from app.api.v1 import webhooks
from app.config import get_settings
from app.database import get_db, init_db, SessionLocal
from app.logging_config import setup_logging, log_access
from app.models import Runner, SecurityEvent
from app.schemas import ErrorResponse, HealthResponse
from app.services.sync_service import SyncService

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


# Global sync task reference
_sync_task: Optional[asyncio.Task] = None
_last_sync_time: Optional[datetime] = None
_last_sync_result: Optional[dict] = None


async def run_sync_loop():
    """Background sync loop that periodically syncs runners with GitHub."""
    global _last_sync_time, _last_sync_result

    logger.info(
        "sync_loop_started",
        interval_seconds=settings.sync_interval_seconds,
        sync_on_startup=settings.sync_on_startup,
    )

    # Initial sync on startup if enabled
    if settings.sync_on_startup:
        await _run_sync()

    # Periodic sync loop
    while True:
        try:
            await asyncio.sleep(settings.sync_interval_seconds)
            logger.info(
                "periodic_sync_triggered",
                interval_seconds=settings.sync_interval_seconds,
            )
            await _run_sync()
        except asyncio.CancelledError:
            logger.info("sync_loop_cancelled")
            break
        except Exception as e:
            logger.error("sync_loop_error", error=str(e))
            # Continue loop even on error


async def _run_sync():
    """Execute a single sync operation."""
    global _last_sync_time, _last_sync_result

    db = SessionLocal()
    try:
        sync_service = SyncService(settings, db)
        result = await sync_service.sync_all_runners()
        _last_sync_time = datetime.now(timezone.utc)
        _last_sync_result = result.to_dict()
        logger.info(
            "periodic_sync_completed",
            **_last_sync_result,
        )
    except Exception as e:
        logger.error("sync_failed", error=str(e))
        _last_sync_result = {"error": str(e)}
    finally:
        db.close()


def get_sync_status() -> dict:
    """Get current sync status for API."""
    return {
        "enabled": settings.sync_enabled,
        "interval_seconds": settings.sync_interval_seconds,
        "last_sync_time": _last_sync_time.isoformat() if _last_sync_time else None,
        "last_sync_result": _last_sync_result,
    }


# Create FastAPI app
app = FastAPI(
    title="GitHub Runner Token Service",
    description="Secure central service for managing GitHub self-hosted runner registrations",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware
# For new dashboard development, allow localhost:5173 (Vite dev server)
cors_origins = ["*"]
if settings.enable_new_dashboard:
    # Add Vite dev server in development
    cors_origins = ["http://localhost:5173", "http://localhost:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Jinja2 templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log HTTP requests with access logging."""
    start_time = time.time()

    try:
        response = await call_next(request)

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
    global _sync_task

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

    # Start background sync task if enabled
    if settings.sync_enabled:
        _sync_task = asyncio.create_task(run_sync_loop())
        logger.info("sync_task_started")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _sync_task

    logger.info("application_shutting_down")

    # Cancel sync task if running
    if _sync_task is not None:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass
        logger.info("sync_task_stopped")


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
    }


# Dashboard endpoint - render Jinja2 dashboard
async def _render_jinja2_dashboard(request: Request, db: Session):
    """Render the Jinja2 dashboard template."""
    # Get all runners (excluding deleted for stats)
    runners = db.query(Runner).filter(Runner.status != "deleted").all()

    # Calculate stats
    stats = {
        "total": len(runners),
        "active": sum(1 for r in runners if r.status == "active"),
        "offline": sum(1 for r in runners if r.status == "offline"),
        "pending": sum(1 for r in runners if r.status == "pending"),
    }

    # Parse labels for display
    for runner in runners:
        try:
            runner.labels_list = json.loads(runner.labels) if runner.labels else []
        except json.JSONDecodeError:
            runner.labels_list = []

    # Get recent security events
    security_events = (
        db.query(SecurityEvent).order_by(SecurityEvent.timestamp.desc()).limit(10).all()
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "version": __version__,
            "stats": stats,
            "runners": runners,
            "security_events": security_events,
            "year": datetime.now().year,
        },
    )


@app.get("/dashboard", response_class=HTMLResponse, tags=["System"])
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Dashboard showing runner status and statistics.

    When ENABLE_NEW_DASHBOARD=true, this redirects to /app (new React dashboard).
    The legacy Jinja2 dashboard is available at /dashboard-legacy.
    """
    if settings.enable_new_dashboard:
        # Redirect to new React dashboard
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/app", status_code=302)

    return await _render_jinja2_dashboard(request, db)


@app.get("/dashboard-legacy", response_class=HTMLResponse, tags=["System"])
async def dashboard_legacy(request: Request, db: Session = Depends(get_db)):
    """
    Legacy Jinja2 dashboard (always available).

    This is the original dashboard that doesn't require authentication.
    Use /dashboard for the default (may redirect to new dashboard if enabled).
    """
    return await _render_jinja2_dashboard(request, db)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(favicon_path)


app.include_router(runners.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(teams.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")


# React dashboard configuration
# In development: Vite dev server handles this on localhost:5173
# In production: React build output is served from /app path
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
frontend_index = frontend_dist / "index.html"

if settings.enable_new_dashboard:
    if frontend_dist.exists():
        # Mount static assets (JS, CSS, images) from React build
        app.mount(
            "/app/assets",
            StaticFiles(directory=str(frontend_dist / "assets"), check_dir=False),
            name="dashboard-assets",
        )

    # SPA catch-all route: serve index.html for all /app/* routes
    # This enables client-side routing (React Router)
    @app.get("/app", response_class=HTMLResponse, tags=["Dashboard"])
    @app.get("/app/{_full_path:path}", response_class=HTMLResponse, tags=["Dashboard"])
    async def serve_spa(_full_path: str = ""):
        """
        Serve React SPA for all /app/* routes.

        This endpoint serves the React dashboard's index.html for all paths,
        enabling client-side routing. The React app handles routing internally.

        In development, use the Vite dev server (localhost:5173) instead.
        """
        if frontend_index.exists():
            return HTMLResponse(content=frontend_index.read_text(), status_code=200)
        else:
            # Development mode: show instructions
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Dashboard - Development Mode</title>
                    <style>
                        body { font-family: system-ui, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }
                        h1 { color: #333; }
                        code { background: #f4f4f4; padding: 0.2rem 0.5rem; border-radius: 4px; }
                        .instructions { background: #e8f4f8; padding: 1rem; border-radius: 8px; margin: 1rem 0; }
                        a { color: #0366d6; }
                    </style>
                </head>
                <body>
                    <h1>New Dashboard - Development Mode</h1>
                    <div class="instructions">
                        <p><strong>Frontend not built yet.</strong></p>
                        <p>To run the new dashboard in development:</p>
                        <ol>
                            <li>Navigate to <code>frontend/</code> directory</li>
                            <li>Run <code>npm install</code></li>
                            <li>Run <code>npm run dev</code></li>
                            <li>Open <a href="http://localhost:5173">http://localhost:5173</a></li>
                        </ol>
                        <p>Or build for production: <code>npm run build</code></p>
                    </div>
                    <p>
                        <a href="/dashboard-legacy">View Legacy Dashboard</a> |
                        <a href="/docs">API Documentation</a>
                    </p>
                </body>
                </html>
                """,
                status_code=200,
            )


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
