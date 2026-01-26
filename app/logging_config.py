"""Logging configuration for the runner token service.

This module provides:
- Console: Application logs only (uvicorn handles access logs)
- File: access.log with complete access logs (optional tracing)
- File: app.log with application logs (configurable level, default INFO)
"""

import logging
from pathlib import Path
from typing import Any, Dict

import structlog
from structlog.stdlib import LoggerFactory, ProcessorFormatter


class AccessLogFilter(logging.Filter):
    """Filter to separate access logs from application logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Only allow records that are access logs."""
        is_access = getattr(record, "is_access_log", False)
        return is_access  # type: ignore[return-value]


class AppLogFilter(logging.Filter):
    """Filter to separate application logs from access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Only allow records that are NOT access logs."""
        is_access = getattr(record, "is_access_log", False)
        return not is_access


def extract_log_record_attributes(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """
    Extract custom attributes from LogRecord into event_dict.

    This processor extracts attributes we set on the LogRecord
    (like method, path, status_code) and adds them to the event_dict
    so they appear in the final log output.
    """
    record = event_dict.get("_record")
    if record:
        # Extract all custom attributes from the record
        for attr in dir(record):
            if not attr.startswith("_") and attr not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "getMessage",
                "taskName",
            ):
                value = getattr(record, attr, None)
                if value is not None and not callable(value):
                    event_dict[attr] = value
    return event_dict


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path = Path("logs"),
    access_log_tracing: bool = False,
) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Application log level
        log_dir: Directory for log files
        access_log_tracing: Enable detailed tracing in access logs
    """
    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)

    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # ===== Shared Processors =====
    shared_processors = [
        extract_log_record_attributes,  # Extract LogRecord attrs to event_dict
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # File processors include timestamps (added AFTER extraction)
    file_processors = [
        *shared_processors,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # ===== Configure Structlog =====
    structlog.configure(
        processors=shared_processors
        + [
            # Prepare event for standard library's ProcessorFormatter
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ===== File Handler: access.log (Complete Access Logs) =====
    # Note: Console logging is handled by uvicorn, we only log to files
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
    root_logger.handlers = [
        access_file_handler,  # Access logs to file
        app_file_handler,  # App logs to file
    ]
    # Capture everything, handlers will filter
    root_logger.setLevel(logging.DEBUG)

    # ===== Silence Noisy Third-Party Loggers on Console =====
    # httpx logs every HTTP request at INFO level, which clutters console
    # We still want these in app.log file, so we only raise console level
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Store tracing setting for use in middleware
    setattr(root_logger, "access_log_tracing", access_log_tracing)


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
    Log an access event to file only (console shows uvicorn's access logs).

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
    # Use standard library logger directly for access logs
    access_logger = logging.getLogger("access")

    # Check if tracing is enabled
    root_logger = logging.getLogger()
    tracing_enabled = getattr(root_logger, "access_log_tracing", False)

    # Build log data
    log_data: Dict[str, Any] = {
        "event": "http_access",
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

    # Create a LogRecord with all data as attributes
    record = access_logger.makeRecord(
        access_logger.name,
        logging.INFO,
        "(access)",
        0,
        "http_access",  # Message for the event
        (),
        None,
    )

    # Mark as access log for filtering
    record.is_access_log = True  # type: ignore[attr-defined]

    # Add all log data as record attributes
    # The extract_log_record_attributes processor will extract these
    for key, value in log_data.items():
        setattr(record, key, value)

    access_logger.handle(record)


# Made with Bob
