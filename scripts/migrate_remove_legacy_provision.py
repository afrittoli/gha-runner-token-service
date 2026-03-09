#!/usr/bin/env python3
"""
Migration script to remove legacy provisioning columns.

This script removes columns and tables associated with the legacy
registration-token provisioning path, which has been replaced by
JIT (Just-In-Time) provisioning.

Columns removed from 'runners' table:
  - registration_token
  - registration_token_expires_at
  - provisioned_labels
  - provisioning_method (kept as "jit" going forward, but column removed)

Columns removed from 'users' table:
  - can_use_registration_token

Tables dropped:
  - label_policies

Usage:
    python scripts/migrate_remove_legacy_provision.py [--dry-run]
"""

import argparse
import os
import sys

from sqlalchemy import create_engine, inspect, text

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_engine(database_url: str):
    """Create SQLAlchemy engine."""
    return create_engine(database_url)


def column_exists(inspector, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    try:
        columns = [c["name"] for c in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def table_exists(inspector, table_name: str) -> bool:
    """Check if a table exists."""
    return table_name in inspector.get_table_names()


def run_migration(database_url: str, dry_run: bool = False):
    """Run the migration."""
    engine = get_engine(database_url)
    inspector = inspect(engine)

    steps = []

    # Columns to drop from 'runners'
    runner_columns = [
        "registration_token",
        "registration_token_expires_at",
        "provisioned_labels",
        "provisioning_method",
    ]
    for col in runner_columns:
        if column_exists(inspector, "runners", col):
            steps.append(
                (
                    f"Drop column runners.{col}",
                    f"ALTER TABLE runners DROP COLUMN {col}",
                )
            )
        else:
            print(f"  [skip] runners.{col} does not exist")

    # Columns to drop from 'users'
    user_columns = ["can_use_registration_token"]
    for col in user_columns:
        if column_exists(inspector, "users", col):
            steps.append(
                (
                    f"Drop column users.{col}",
                    f"ALTER TABLE users DROP COLUMN {col}",
                )
            )
        else:
            print(f"  [skip] users.{col} does not exist")

    # Tables to drop
    tables_to_drop = ["label_policies"]
    for table in tables_to_drop:
        if table_exists(inspector, table):
            steps.append(
                (
                    f"Drop table {table}",
                    f"DROP TABLE {table}",
                )
            )
        else:
            print(f"  [skip] table {table} does not exist")

    if not steps:
        print("Nothing to migrate.")
        return

    print(f"\nMigration steps ({len(steps)}):")
    for description, _ in steps:
        prefix = "[DRY RUN] " if dry_run else ""
        print(f"  {prefix}{description}")

    if dry_run:
        print("\nDry run complete. No changes made.")
        return

    with engine.connect() as conn:
        for description, sql in steps:
            print(f"  Executing: {description}")
            conn.execute(text(sql))
        conn.commit()

    print("\nMigration complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Remove legacy provisioning columns and tables"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making changes",
    )
    parser.add_argument(
        "--database-url",
        help="Database URL (defaults to DATABASE_URL env var)",
    )
    args = parser.parse_args()

    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable or --database-url required")
        sys.exit(1)

    print(f"Database: {database_url}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}\n")

    run_migration(database_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
