#!/usr/bin/env python3
"""
One-off migration script for team-based authorization.

This script migrates the demo environment database from user-based to team-based
authorization. It assumes each existing user should get their own team.

Usage:
    python scripts/migrate_to_team_authz.py [--dry-run]

The script will:
1. Create teams and user_team_memberships tables
2. Add team_id and team_name columns to runners table
3. For each existing user:
   - Create a team named after the user (e.g., "alice-team")
   - Migrate their label policy to the team
   - Add the user to their team
4. Update existing runners to associate with user's team
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings
from app.models import Base, LabelPolicy, Runner, Team, User, UserTeamMembership


def get_db_session(database_url: str):
    """Create database session."""
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal(), engine


def create_tables(engine):
    """Create new tables for team-based authorization."""
    print("Creating new tables...")
    
    with engine.connect() as conn:
        # Create teams table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS teams (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL UNIQUE,
                description TEXT,
                required_labels TEXT NOT NULL,
                optional_label_patterns TEXT,
                max_runners INTEGER,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                deactivation_reason TEXT,
                deactivated_at TIMESTAMP,
                deactivated_by VARCHAR,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                created_by VARCHAR
            )
        """))
        
        # Create indexes for teams
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_teams_name ON teams(name)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_teams_active ON teams(is_active)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_teams_name_active "
            "ON teams(name, is_active)"
        ))
        
        # Create user_team_memberships table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_team_memberships (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                team_id VARCHAR NOT NULL,
                joined_at TIMESTAMP NOT NULL,
                added_by VARCHAR,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
            )
        """))
        
        # Create indexes for user_team_memberships
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_user_team_user "
            "ON user_team_memberships(user_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_user_team_team "
            "ON user_team_memberships(team_id)"
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_team_unique "
            "ON user_team_memberships(user_id, team_id)"
        ))
        
        conn.commit()
    
    print("✓ Tables created successfully")


def add_team_columns_to_runners(engine):
    """Add team_id and team_name columns to runners table."""
    print("Adding team columns to runners table...")
    
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text(
            "SELECT COUNT(*) FROM pragma_table_info('runners') "
            "WHERE name IN ('team_id', 'team_name')"
        ))
        existing_cols = result.scalar()
        
        if existing_cols == 0:
            conn.execute(text(
                "ALTER TABLE runners ADD COLUMN team_id VARCHAR"
            ))
            conn.execute(text(
                "ALTER TABLE runners ADD COLUMN team_name VARCHAR"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_runners_team_status "
                "ON runners(team_id, status)"
            ))
            conn.commit()
            print("✓ Team columns added to runners table")
        else:
            print("✓ Team columns already exist in runners table")


def sanitize_team_name(email: str) -> str:
    """Convert email to a valid team name (kebab-case)."""
    # Extract username part before @
    username = email.split('@')[0]
    # Replace non-alphanumeric with hyphens, convert to lowercase
    team_name = ''.join(c if c.isalnum() else '-' for c in username).lower()
    # Remove leading/trailing hyphens and collapse multiple hyphens
    team_name = '-'.join(filter(None, team_name.split('-')))
    # Ensure it doesn't start or end with hyphen
    team_name = team_name.strip('-')
    # Add suffix to make it a team name
    return f"{team_name}-team"


def migrate_users_to_teams(session, dry_run=False):
    """Migrate each user to their own team."""
    print("\nMigrating users to teams...")
    
    # Get all users
    users = session.query(User).all()
    print(f"Found {len(users)} users")
    
    if len(users) == 0:
        print("⚠ No users found in database")
        return {}
    
    user_team_map = {}
    
    for user in users:
        email = user.email or f"user-{user.id}"
        team_name = sanitize_team_name(email)
        
        # Check if team already exists
        existing_team = session.query(Team).filter_by(name=team_name).first()
        if existing_team:
            print(f"  ⚠ Team '{team_name}' already exists, skipping user {email}")
            user_team_map[user.id] = existing_team
            continue
        
        # Get user's label policy if it exists
        label_policy = session.query(LabelPolicy).filter_by(
            user_identity=email
        ).first()
        
        if label_policy:
            required_labels = label_policy.allowed_labels
            optional_patterns = label_policy.label_patterns
            max_runners = label_policy.max_runners
            print(f"  • User {email}: migrating label policy")
        else:
            # Default policy: allow self-hosted label
            required_labels = json.dumps(["self-hosted"])
            optional_patterns = None
            max_runners = None
            print(f"  • User {email}: no label policy, using defaults")
        
        # Create team
        team = Team(
            name=team_name,
            description=f"Team for {email}",
            required_labels=required_labels,
            optional_label_patterns=optional_patterns,
            max_runners=max_runners,
            is_active=user.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="migration_script",
        )
        
        if not dry_run:
            session.add(team)
            session.flush()  # Get team.id
        
        print(f"    → Created team: {team_name}")
        
        # Create membership
        membership = UserTeamMembership(
            user_id=user.id,
            team_id=team.id,
            joined_at=datetime.now(timezone.utc),
            added_by="migration_script",
        )
        
        if not dry_run:
            session.add(membership)
        
        print(f"    → Added {email} to team {team_name}")
        
        user_team_map[user.id] = team
    
    if not dry_run:
        session.commit()
        print(f"\n✓ Migrated {len(user_team_map)} users to teams")
    else:
        print(f"\n✓ [DRY RUN] Would migrate {len(user_team_map)} users to teams")
    
    return user_team_map


def update_runners_with_teams(session, user_team_map, dry_run=False):
    """Update existing runners to associate with user's team."""
    print("\nUpdating runners with team associations...")
    
    # In dry-run mode, query without team columns since they don't exist yet
    if dry_run:
        # Query only the columns that exist
        from sqlalchemy import select
        stmt = select(
            Runner.id,
            Runner.runner_name,
            Runner.provisioned_by
        )
        result = session.execute(stmt)
        runners_data = result.all()
        print(f"Found {len(runners_data)} runners")
    else:
        runners = session.query(Runner).all()
        print(f"Found {len(runners)} runners")
        runners_data = [(r.id, r.runner_name, r.provisioned_by) for r in runners]
    
    if len(runners_data) == 0:
        print("⚠ No runners found in database")
        return
    
    updated_count = 0
    skipped_count = 0
    
    for runner_id, runner_name, provisioned_by in runners_data:
        # Find user by provisioned_by email
        user = session.query(User).filter_by(email=provisioned_by).first()
        
        if not user:
            print(
                f"  ⚠ Runner {runner_name}: "
                f"user {provisioned_by} not found, skipping"
            )
            skipped_count += 1
            continue
        
        if user.id not in user_team_map:
            print(
                f"  ⚠ Runner {runner_name}: "
                f"no team for user {user.email}, skipping"
            )
            skipped_count += 1
            continue
        
        team = user_team_map[user.id]
        
        if not dry_run:
            # Update the actual runner object
            runner = session.query(Runner).filter_by(id=runner_id).first()
            if runner:
                runner.team_id = team.id
                runner.team_name = team.name
        
        updated_count += 1
        print(f"  • Runner {runner_name} → team {team.name}")
    
    if not dry_run:
        session.commit()
        print(f"\n✓ Updated {updated_count} runners")
    else:
        print(f"\n✓ [DRY RUN] Would update {updated_count} runners")
    
    if skipped_count > 0:
        print(f"⚠ Skipped {skipped_count} runners (no matching user/team)")


def main():
    """Run the migration."""
    parser = argparse.ArgumentParser(
        description="Migrate database to team-based authorization"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()
    
    # Load settings
    settings = Settings()
    
    print("=" * 70)
    print("Team-Based Authorization Migration")
    print("=" * 70)
    print(f"Database: {settings.database_url}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 70)
    
    if not args.dry_run:
        response = input("\n⚠️  This will modify the database. Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Migration cancelled")
            return
    
    print()
    
    # Create session
    session, engine = get_db_session(settings.database_url)
    
    try:
        # Step 1: Create new tables
        if not args.dry_run:
            create_tables(engine)
            add_team_columns_to_runners(engine)
        else:
            print("[DRY RUN] Would create tables and add columns")
        
        # Step 2: Migrate users to teams
        user_team_map = migrate_users_to_teams(session, dry_run=args.dry_run)
        
        # Step 3: Update runners
        update_runners_with_teams(session, user_team_map, dry_run=args.dry_run)
        
        print("\n" + "=" * 70)
        if args.dry_run:
            print("✓ DRY RUN COMPLETE - No changes made")
        else:
            print("✓ MIGRATION COMPLETE")
        print("=" * 70)
        
        # Summary
        print("\nSummary:")
        print(f"  • Teams created: {len(user_team_map)}")
        print(f"  • Users migrated: {len(user_team_map)}")
        if not args.dry_run:
            runners_with_teams = (
                session.query(Runner)
                .filter(Runner.team_id.isnot(None))
                .count()
            )
            print(f"  • Runners updated: {runners_with_teams}")
        else:
            print("  • Runners that would be updated: (see output above)")
        
        if not args.dry_run:
            print("\nNext steps:")
            print("  1. Verify the migration in your demo environment")
            print("  2. Test team-based provisioning")
            print("  3. Consider removing old label_policies table once verified")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        if not args.dry_run:
            session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()

# Made with Bob
