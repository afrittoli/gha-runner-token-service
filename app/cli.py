"""CLI commands for administration."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import click
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.github.client import GitHubClient
from app.models import AuditLog, Runner, User
from app.services.user_service import UserService


@click.group()
def cli():
    """Runner Token Service CLI."""
    pass


@cli.command()
def init_db_cmd():
    """Initialize the database schema."""
    try:
        init_db()
        click.echo("✓ Database initialized successfully")
    except Exception as e:
        click.echo(f"✗ Failed to initialize database: {e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.option("--hours", default=24, help="Hours before considering runner stale")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be deleted without deleting"
)
def cleanup_stale_runners(hours: int, dry_run: bool):
    """Cleanup stale offline runners."""
    settings = get_settings()
    db: Session = SessionLocal()

    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Find stale runners
        stale_runners = (
            db.query(Runner)
            .filter(
                Runner.status.in_(["pending", "offline"]),
                Runner.created_at < cutoff_time,
            )
            .all()
        )

        if not stale_runners:
            click.echo("No stale runners found")
            return

        click.echo(f"Found {len(stale_runners)} stale runners:")

        github = GitHubClient(settings)

        for runner in stale_runners:
            age_hours = (
                datetime.now(timezone.utc) - runner.created_at
            ).total_seconds() / 3600

            click.echo(
                f"  - {runner.runner_name} (status: {runner.status}, age: {age_hours:.1f}h)"
            )

            if not dry_run:
                # Delete from GitHub if exists
                if runner.github_runner_id:
                    try:
                        deleted = asyncio.run(
                            github.delete_runner(runner.github_runner_id)
                        )
                        if deleted:
                            click.echo("    ✓ Deleted from GitHub")
                    except Exception as e:
                        click.echo(f"    ✗ Failed to delete from GitHub: {e}", err=True)

                # Update local state
                runner.status = "deleted"
                runner.deleted_at = datetime.now(timezone.utc)
                runner.registration_token = None
                db.commit()

                click.echo("    ✓ Marked as deleted in database")

        if dry_run:
            click.echo("\n(Dry run - no changes made)")
        else:
            click.echo(f"\n✓ Cleaned up {len(stale_runners)} stale runners")

    except Exception as e:
        click.echo(f"✗ Cleanup failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        db.close()


@cli.command()
@click.option("--status", help="Filter by status")
@click.option("--user", help="Filter by provisioned_by")
def list_runners_cmd(status: str, user: str):
    """List all runners."""
    db: Session = SessionLocal()

    try:
        query = db.query(Runner)

        if status:
            query = query.filter(Runner.status == status)
        if user:
            query = query.filter(Runner.provisioned_by == user)

        runners = query.order_by(Runner.created_at.desc()).all()

        if not runners:
            click.echo("No runners found")
            return

        click.echo(f"\nFound {len(runners)} runners:\n")

        for runner in runners:
            labels = json.loads(runner.labels)
            labels_str = ", ".join(labels) if labels else "none"

            click.echo(f"Name:           {runner.runner_name}")
            click.echo(f"Status:         {runner.status}")
            click.echo(f"GitHub ID:      {runner.github_runner_id or 'N/A'}")
            click.echo(f"Labels:         {labels_str}")
            click.echo(f"Ephemeral:      {runner.ephemeral}")
            click.echo(f"Provisioned by: {runner.provisioned_by}")
            click.echo(f"Created:        {runner.created_at}")

            if runner.registered_at:
                click.echo(f"Registered:     {runner.registered_at}")
            if runner.deleted_at:
                click.echo(f"Deleted:        {runner.deleted_at}")

            click.echo()

    finally:
        db.close()


@cli.command()
@click.option("--since", help="Filter events since date (YYYY-MM-DD)")
@click.option("--event-type", help="Filter by event type")
@click.option("--user", help="Filter by user")
@click.option("--limit", default=100, help="Maximum number of events")
@click.option("--output", help="Output to JSON file")
def export_audit_log(since: str, event_type: str, user: str, limit: int, output: str):
    """Export audit log."""
    db: Session = SessionLocal()

    try:
        query = db.query(AuditLog)

        if since:
            since_date = datetime.strptime(since, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            query = query.filter(AuditLog.timestamp >= since_date)
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        if user:
            query = query.filter(AuditLog.user_identity == user)

        events = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

        if not events:
            click.echo("No audit events found")
            return

        # Convert to dict
        audit_data = []
        for event in events:
            audit_data.append(
                {
                    "id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "runner_name": event.runner_name,
                    "user_identity": event.user_identity,
                    "success": event.success,
                    "error_message": event.error_message,
                    "event_data": json.loads(event.event_data)
                    if event.event_data
                    else None,
                }
            )

        if output:
            # Write to file
            with open(output, "w") as f:
                json.dump(audit_data, f, indent=2)
            click.echo(f"✓ Exported {len(audit_data)} events to {output}")
        else:
            # Print to stdout
            click.echo(json.dumps(audit_data, indent=2))

    finally:
        db.close()


@cli.command()
def sync_github():
    """Sync runner status with GitHub API."""
    settings = get_settings()
    db: Session = SessionLocal()

    try:
        # Get all non-deleted runners from database
        local_runners = db.query(Runner).filter(Runner.status != "deleted").all()

        if not local_runners:
            click.echo("No runners to sync")
            return

        click.echo(f"Syncing {len(local_runners)} runners with GitHub...\n")

        github = GitHubClient(settings)

        # Fetch all runners from GitHub
        github_runners = asyncio.run(github.list_runners())
        github_runners_by_name = {r.name: r for r in github_runners}

        updates = 0

        for runner in local_runners:
            github_runner = github_runners_by_name.get(runner.runner_name)

            if github_runner:
                # Runner exists in GitHub
                old_status = runner.status
                runner.status = github_runner.status
                runner.github_runner_id = github_runner.id

                if runner.registered_at is None:
                    runner.registered_at = datetime.now(timezone.utc)

                if old_status != runner.status:
                    click.echo(
                        f"✓ {runner.runner_name}: {old_status} → {runner.status}"
                    )
                    updates += 1

                # Clear registration token after successful registration
                if runner.registration_token:
                    runner.registration_token = None
                    runner.registration_token_expires_at = None
            else:
                # Runner not found in GitHub
                if runner.status != "pending":
                    # Was registered but now deleted
                    old_status = runner.status
                    runner.status = "deleted"
                    runner.deleted_at = datetime.now(timezone.utc)

                    click.echo(f"✓ {runner.runner_name}: {old_status} → deleted")
                    updates += 1

        db.commit()

        click.echo(f"\n✓ Sync complete: {updates} runners updated")

    except Exception as e:
        click.echo(f"✗ Sync failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        db.close()


# User management commands


@cli.command()
@click.option("--email", required=True, help="Admin user email address")
@click.option("--oidc-sub", help="OIDC subject claim (optional)")
@click.option("--display-name", help="Display name (defaults to email)")
def create_admin(email: str, oidc_sub: str, display_name: str):
    """Create an admin user.

    Use this command to bootstrap the first admin user, or to create
    additional admin users from the command line.
    """
    db: Session = SessionLocal()

    try:
        user_service = UserService(db)

        # Check if user already exists
        existing = user_service.get_user_by_email(email)
        if existing:
            if existing.is_admin:
                click.echo(
                    f"✗ Admin user with email '{email}' already exists", err=True
                )
                raise SystemExit(1)
            else:
                # Upgrade existing user to admin
                user_service.update_user(existing.id, is_admin=True)
                click.echo(f"✓ Upgraded existing user '{email}' to admin")
                return

        # Create new admin user
        user = user_service.create_user(
            email=email,
            oidc_sub=oidc_sub,
            display_name=display_name or email,
            is_admin=True,
            can_use_registration_token=True,
            can_use_jit=True,
            created_by="cli",
        )

        click.echo("✓ Created admin user:")
        click.echo(f"  ID:           {user.id}")
        click.echo(f"  Email:        {user.email}")
        click.echo(f"  Display Name: {user.display_name}")
        click.echo(f"  Is Admin:     {user.is_admin}")

    except ValueError as e:
        click.echo(f"✗ Failed to create admin: {e}", err=True)
        raise SystemExit(1)
    finally:
        db.close()


@cli.command()
@click.option(
    "--dry-run", is_flag=True, help="Show what would be migrated without making changes"
)
def migrate_admin_identities(dry_run: bool):
    """Migrate ADMIN_IDENTITIES env var to User table.

    This command reads the ADMIN_IDENTITIES environment variable and
    creates admin users in the database for each identity found.
    """
    settings = get_settings()
    db: Session = SessionLocal()

    try:
        admin_identities = settings.admin_identities

        if not admin_identities:
            click.echo("No ADMIN_IDENTITIES configured in environment")
            return

        click.echo(f"Found {len(admin_identities)} admin identities to migrate:\n")

        user_service = UserService(db)
        created = 0
        skipped = 0

        for identity in admin_identities:
            # Determine if this is an email or OIDC sub
            is_email = "@" in identity

            click.echo(f"  - {identity}")

            if dry_run:
                continue

            # Check if user already exists
            if is_email:
                existing = user_service.get_user_by_email(identity)
            else:
                existing = user_service.get_user_by_oidc_sub(identity)

            if existing:
                if not existing.is_admin:
                    # Upgrade to admin
                    user_service.update_user(existing.id, is_admin=True)
                    click.echo("    ✓ Upgraded to admin")
                    created += 1
                else:
                    click.echo("    → Already an admin, skipped")
                    skipped += 1
            else:
                # Create new admin user
                user_service.create_user(
                    email=identity if is_email else None,
                    oidc_sub=identity if not is_email else None,
                    display_name=identity,
                    is_admin=True,
                    can_use_registration_token=True,
                    can_use_jit=True,
                    created_by="migrate-admin-identities",
                )
                click.echo("    ✓ Created admin user")
                created += 1

        if dry_run:
            click.echo("\n(Dry run - no changes made)")
        else:
            click.echo(
                f"\n✓ Migration complete: {created} users created/upgraded, {skipped} skipped"
            )
            if created > 0:
                click.echo(
                    "\nNote: You can now remove ADMIN_IDENTITIES from your environment."
                )

    except Exception as e:
        click.echo(f"✗ Migration failed: {e}", err=True)
        raise SystemExit(1)
    finally:
        db.close()


@cli.command()
@click.option("--include-inactive", is_flag=True, help="Include inactive users")
@click.option("--admins-only", is_flag=True, help="Show only admin users")
def list_users(include_inactive: bool, admins_only: bool):
    """List all users."""
    db: Session = SessionLocal()

    try:
        query = db.query(User)

        if not include_inactive:
            query = query.filter(User.is_active == True)  # noqa: E712

        if admins_only:
            query = query.filter(User.is_admin == True)  # noqa: E712

        users = query.order_by(User.created_at.desc()).all()

        if not users:
            click.echo("No users found")
            return

        click.echo(f"\nFound {len(users)} users:\n")

        for user in users:
            status_flags = []
            if user.is_admin:
                status_flags.append("admin")
            if not user.is_active:
                status_flags.append("inactive")
            if user.can_use_registration_token:
                status_flags.append("reg-token")
            if user.can_use_jit:
                status_flags.append("jit")

            flags_str = ", ".join(status_flags) if status_flags else "none"

            click.echo(f"ID:           {user.id}")
            click.echo(f"Email:        {user.email or 'N/A'}")
            click.echo(f"OIDC Sub:     {user.oidc_sub or 'N/A'}")
            click.echo(f"Display Name: {user.display_name or 'N/A'}")
            click.echo(f"Permissions:  {flags_str}")
            click.echo(f"Created:      {user.created_at}")
            if user.last_login_at:
                click.echo(f"Last Login:   {user.last_login_at}")
            click.echo()

    finally:
        db.close()


if __name__ == "__main__":
    cli()
