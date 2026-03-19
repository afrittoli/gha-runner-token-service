"""Database setup and session management."""

import time
from typing import Any
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


def _get_iam_auth_token() -> str:
    """Generate a short-lived RDS IAM authentication token using boto3."""
    import boto3

    client = boto3.client("rds", region_name=settings.aws_region)
    token = client.generate_db_auth_token(
        DBHostname=settings.db_host,
        Port=settings.db_port,
        DBUsername=settings.db_username,
        Region=settings.aws_region,
    )
    logger.debug(
        "rds_iam_token_generated", host=settings.db_host, user=settings.db_username
    )
    return token


def _build_iam_database_url(token: str) -> str:
    """Build a PostgreSQL connection URL using an IAM auth token as the password."""
    import urllib.parse

    encoded_token = urllib.parse.quote(token, safe="")
    return (
        f"postgresql://{settings.db_username}:{encoded_token}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    )


def _get_ssl_connect_args() -> dict[str, Any]:
    """Build psycopg2 connect_args for SSL/TLS."""
    connect_args: dict[str, Any] = {}
    if settings.db_ssl_mode:
        connect_args["sslmode"] = settings.db_ssl_mode
    if settings.db_ssl_cert:
        connect_args["sslcert"] = settings.db_ssl_cert
    if settings.db_ssl_key:
        connect_args["sslkey"] = settings.db_ssl_key
    if settings.db_ssl_root_cert:
        connect_args["sslrootcert"] = settings.db_ssl_root_cert
    return connect_args


def get_engine_config():
    """Get database engine configuration based on database type."""
    # IAM auth mode: no static DATABASE_URL; token is fetched per connection
    if settings.db_iam_auth:
        if not all(
            [
                settings.db_host,
                settings.db_name,
                settings.db_username,
                settings.aws_region,
            ]
        ):
            raise ValueError(
                "db_host, db_name, db_username, and aws_region are required when db_iam_auth=true"
            )
        # Use a creator function so a fresh token is obtained for every new
        # physical connection opened by the pool. RDS tokens expire after 15 min
        # and pool_recycle should be set below that threshold (e.g. 900 s).
        import psycopg2

        def _iam_creator():
            token = _get_iam_auth_token()
            connect_args = _get_ssl_connect_args()
            # sslmode=require is mandatory for IAM auth
            connect_args.setdefault("sslmode", "require")
            return psycopg2.connect(
                host=settings.db_host,
                port=settings.db_port,
                dbname=settings.db_name,
                user=settings.db_username,
                password=token,
                **connect_args,
            )

        return {
            "creator": _iam_creator,
            "echo": False,
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_pre_ping": True,
            "pool_recycle": settings.db_pool_recycle,
        }

    config: dict[str, Any] = {
        "url": settings.database_url,
        "echo": False,
    }

    if "sqlite" in settings.database_url:
        config["connect_args"] = {"check_same_thread": False}
    elif "postgresql" in settings.database_url:
        config["pool_size"] = settings.db_pool_size
        config["max_overflow"] = settings.db_max_overflow
        config["pool_pre_ping"] = True
        config["pool_recycle"] = settings.db_pool_recycle

        connect_args = _get_ssl_connect_args()
        if connect_args:
            config["connect_args"] = connect_args
    else:
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

            db_type = (
                "postgresql_iam"
                if settings.db_iam_auth
                else "postgresql"
                if "postgresql" in settings.database_url
                else "sqlite"
            )
            logger.info(
                "database_connected",
                database_type=db_type,
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
