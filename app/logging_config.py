"""Logging configuration for the runner token service.

This module provides:
- Console: Minimalistic access logs (no timestamps, like uvicorn default)
- File: access.log with complete access logs (optional tracing for headers/payloads)
- File: app.log with application logs (configurable level, default INFO)
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict

import structlog
from structlog.stdlib import LoggerFactory, ProcessorFormatter


class MinimalisticAccessLogFormatter(logging.Formatter):
    """Minimalistic formatter for console access logs (no timestamps)."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record without timestamp, similar to uvicorn default."""
        if hasattr(record, "method") and hasattr(record, "path"):
            # Access log format: METHOD /path STATUS_CODE
            status = getattr(record, "status_code", "???")
            return f"{record.method} {record.path} {status}"
        # Fallback for non-access logs
        return record.getMessage()


class AccessLogFilter(logging.Filter):
    """Filter to separate access logs from application logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Only allow records that are access logs."""
        return hasattr(record, "is_access_log") and record.is_access_log


class AppLogFilter(logging.Filter):
    """Filter to separate application logs from access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Only allow records that are NOT access logs."""
        return not (hasattr(record, "is_access_log") and record.is_access_log)


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path = Path("logs"),
    access_log_tracing: bool = False,
) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Application log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files
        access_log_tracing: Enable detailed tracing in access logs (headers, payloads)
    """
    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)

    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # ===== Shared Processors =====
    # These are used by both console and file handlers
    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # File processors include timestamps
    file_processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        *shared_processors,
    ]

    # Console processors don't include timestamps for access logs
    console_processors = [
        structlog.stdlib.filter_by_level,
        *shared_processors,
    ]

    # ===== Configure Structlog =====
    structlog.configure(
        processors=console_processors
        + [
            # Prepare event for standard library's ProcessorFormatter
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ===== Console Handler (Access Logs Only, Minimalistic) =====
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # Always INFO for access logs
    console_handler.addFilter(AccessLogFilter())
    console_handler.setFormatter(MinimalisticAccessLogFormatter())

    # ===== File Handler: access.log (Complete Access Logs) =====
    access_file_handler = logging.FileHandler(log_dir / "access.log")
    access_file_handler.setLevel(logging.INFO)
    access_file_handler.addFilter(AccessLogFilter())
    access_file_handler.setFormatter(
        ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=file_processors,
        )
    )

    # ===== File Handler: app.log (Application Logs) =====
    app_file_handler = logging.FileHandler(log_dir / "app.log")
    app_file_handler.setLevel(numeric_level)
    app_file_handler.addFilter(AppLogFilter())
    app_file_handler.setFormatter(
        ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=file_processors,
        )
    )

    # ===== Configure Root Logger =====
    root_logger = logging.getLogger()
    root_logger.handlers = [console_handler, access_file_handler, app_file_handler]
    root_logger.setLevel(logging.DEBUG)  # Capture everything, handlers will filter

    # Store tracing setting for use in middleware
    root_logger.access_log_tracing = access_log_tracing  # type: ignore[attr-defined]


def log_access(
    method: str,
    path: str,
    status_code: int,
    client: str | None = None,
    headers: Dict[str, Any] | None = None,
    request_body: str | None = None,
    response_body: str | None = None,
    duration_ms: float | None = None,
) -> None:
    """
    Log an access event.

    Args:
        method: HTTP method
        path: Request path
        status_code: HTTP status code
        client: Client IP address
        headers: Request headers (only logged if tracing enabled)
        request_body: Request body (only logged if tracing enabled)
        response_body: Response body (only logged if tracing enabled)
        duration_ms: Request duration in milliseconds
    """
    logger = structlog.get_logger()

    # Check if tracing is enabled
    root_logger = logging.getLogger()
    tracing_enabled = getattr(root_logger, "access_log_tracing", False)

    # Build log data
    log_data: Dict[str, Any] = {
        "is_access_log": True,
        "method": method,
        "path": path,
        "status_code": status_code,
    }

    if client:
        log_data["client"] = client

    if duration_ms is not None:
        log_data["duration_ms"] = round(duration_ms, 2)

    # Add tracing data if enabled
    if tracing_enabled:
        if headers:
            # Redact sensitive headers
            sensitive = {"authorization", "cookie", "proxy-authorization"}
            safe_headers = {
                k: ("*****" if k.lower() in sensitive else v)
                for k, v in headers.items()
            }
            log_data["headers"] = safe_headers

        if request_body:
            log_data["request_body"] = request_body

        if response_body:
            log_data["response_body"] = response_body

    logger.info("access", **log_data)


# Made with Bob
