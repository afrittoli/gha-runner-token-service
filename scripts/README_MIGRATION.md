# Database Migration to Team-Based Authorization

This directory contains the migration script for transitioning from user-based to team-based authorization.

## Migration Script: `migrate_to_team_authz.py`

### Purpose

Migrates the demo environment database from user-based authorization (where each user has their own label policies) to team-based authorization (where users belong to teams that define policies).

### What It Does

1. **Creates new tables:**
   - `teams` - Team definitions with label policies and quotas
   - `user_team_memberships` - Many-to-many user-team relationships

2. **Updates existing tables:**
   - Adds `team_id` and `team_name` columns to `runners` table

3. **Migrates data:**
   - Creates a separate team for each existing user
   - Team name format: `{username}-team` (e.g., `alice-team`)
   - Migrates user's label policy to their team
   - Adds user as member of their team
   - Updates existing runners to associate with user's team

### Usage

#### Dry Run (Recommended First)

```bash
# See what would be changed without modifying the database
python scripts/migrate_to_team_authz.py --dry-run
```

#### Live Migration

```bash
# Actually perform the migration
python scripts/migrate_to_team_authz.py
```

The script will:
- Show a summary of what will be done
- Ask for confirmation before proceeding
- Display progress for each step
- Provide a final summary

### Example Output

```
======================================================================
Team-Based Authorization Migration
======================================================================
Database: postgresql://user@localhost/gharts
Mode: LIVE
======================================================================

⚠️  This will modify the database. Continue? (yes/no): yes

Creating new tables...
✓ Tables created successfully

Adding team columns to runners table...
✓ Team columns added to runners table

Migrating users to teams...
Found 3 users
  • User alice@example.com: migrating label policy
    → Created team: alice-team
    → Added alice@example.com to team alice-team
  • User bob@example.com: no label policy, using defaults
    → Created team: bob-team
    → Added bob@example.com to team bob-team
  • User charlie@example.com: migrating label policy
    → Created team: charlie-team
    → Added charlie@example.com to team charlie-team

✓ Migrated 3 users to teams

Updating runners with team associations...
Found 5 runners
  • Runner alice-runner-1 → team alice-team
  • Runner alice-runner-2 → team alice-team
  • Runner bob-runner-1 → team bob-team
  • Runner charlie-runner-1 → team charlie-team
  • Runner charlie-runner-2 → team charlie-team

✓ Updated 5 runners

======================================================================
✓ MIGRATION COMPLETE
======================================================================

Summary:
  • Teams created: 3
  • Users migrated: 3
  • Runners updated: 5

Next steps:
  1. Verify the migration in your demo environment
  2. Test team-based provisioning
  3. Consider removing old label_policies table once verified
```

### Team Naming Convention

The script converts user emails to team names using this logic:

- Extract username part before `@`
- Convert to lowercase
- Replace non-alphanumeric characters with hyphens
- Remove leading/trailing hyphens
- Collapse multiple consecutive hyphens
- Append `-team` suffix

Examples:
- `alice@example.com` → `alice-team`
- `bob.smith@company.com` → `bob-smith-team`
- `user_123@test.org` → `user-123-team`

### Label Policy Migration

For each user:

**If user has a label policy:**
- `required_labels` → team's `required_labels`
- `label_patterns` → team's `optional_label_patterns`
- `max_runners` → team's `max_runners`

**If user has no label policy:**
- Default `required_labels`: `["self-hosted"]`
- No optional patterns
- No runner limit

### Safety Features

1. **Dry run mode** - Test without making changes
2. **Confirmation prompt** - Requires explicit "yes" to proceed
3. **Transaction safety** - Rolls back on errors
4. **Idempotency** - Can be run multiple times safely
5. **Detailed logging** - Shows exactly what's happening

### Verification After Migration

```bash
# Check teams were created
sqlite3 gharts.db "SELECT name, description FROM teams;"

# Check memberships
sqlite3 gharts.db "SELECT u.email, t.name FROM user_team_memberships m 
  JOIN users u ON m.user_id = u.id 
  JOIN teams t ON m.team_id = t.id;"

# Check runners have teams
sqlite3 gharts.db "SELECT runner_name, team_name FROM runners 
  WHERE team_id IS NOT NULL;"
```

### Rollback

If you need to rollback the migration:

```bash
# Remove team columns from runners
sqlite3 gharts.db "ALTER TABLE runners DROP COLUMN team_id;"
sqlite3 gharts.db "ALTER TABLE runners DROP COLUMN team_name;"

# Drop new tables
sqlite3 gharts.db "DROP TABLE user_team_memberships;"
sqlite3 gharts.db "DROP TABLE teams;"
```

**Note:** This only works if you haven't deleted the `label_policies` table yet.

### Requirements

- Python 3.8+
- SQLAlchemy
- Access to the database (DATABASE_URL environment variable)
- All app dependencies installed

### Troubleshooting

**Error: "No module named 'app'"**
- Run from the project root directory
- Ensure PYTHONPATH includes the project root

**Error: "Table already exists"**
- The migration has already been run
- Use `--dry-run` to see current state
- Check if tables exist: `sqlite3 gharts.db ".tables"`

**Error: "User not found for runner"**
- Some runners may not have matching users
- These will be skipped with a warning
- You can manually assign them to teams later

### Post-Migration Tasks

1. **Test the new team-based provisioning API**
2. **Update any scripts/tools that reference label policies**
3. **Consider removing the old `label_policies` table** (after verification)
4. **Update documentation** to reflect team-based model
5. **Train users** on the new team-based workflow

### Support

For issues or questions:
- Check the migration output for specific error messages
- Review the design document: `docs/design/team_based_authorization.md`
- Run with `--dry-run` to diagnose issues