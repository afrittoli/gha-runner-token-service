"""Database setup and session management."""

import time
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


def get_engine_config():
    """Get database engine configuration based on database type."""
    config = {
        "url": settings.database_url,
        "echo": settings.log_level == "DEBUG",
    }

    if "sqlite" in settings.database_url:
        # SQLite-specific configuration
        config["connect_args"] = {"check_same_thread": False}
    elif "postgresql" in settings.database_url:
        # PostgreSQL-specific configuration
        config["pool_size"] = settings.db_pool_size
        config["max_overflow"] = settings.db_max_overflow
        config["pool_pre_ping"] = True  # Verify connections before use
        config["pool_recycle"] = settings.db_pool_recycle

        # SSL/TLS configuration for cloud databases
        if settings.db_ssl_mode:
            connect_args = {"sslmode": settings.db_ssl_mode}
            if settings.db_ssl_cert:
                connect_args["sslcert"] = settings.db_ssl_cert
            if settings.db_ssl_key:
                connect_args["sslkey"] = settings.db_ssl_key
            if settings.db_ssl_root_cert:
                connect_args["sslrootcert"] = settings.db_ssl_root_cert
            config["connect_args"] = connect_args
    else:
        # Default configuration for other databases
        config["poolclass"] = NullPool

    return config


def create_engine_with_retry(max_retries=3, retry_delay=2):
    """Create database engine with retry logic for transient failures."""
    config = get_engine_config()

    for attempt in range(max_retries):
        try:
            engine = create_engine(**config)

            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info(
                "database_connected",
                database_type="postgresql"
                if "postgresql" in settings.database_url
                else "sqlite",
                attempt=attempt + 1,
            )
            return engine

        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    "database_connection_failed_retrying",
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                )
                time.sleep(retry_delay)
            else:
                logger.error(
                    "database_connection_failed",
                    error=str(e),
                    attempts=max_retries,
                )
                raise


# Create database engine with retry logic
engine = create_engine_with_retry()


# Add connection pool logging for debugging
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log database connections."""
    logger.debug("database_connection_established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log connection checkouts from pool."""
    logger.debug("database_connection_checkout")


# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Get database session.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database schema."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("database_schema_initialized")
    except Exception as e:
        logger.error("database_schema_initialization_failed", error=str(e))
        raise


def check_db_health():
    """Check database health for health check endpoint."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return False
