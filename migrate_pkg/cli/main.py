import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from migrate_pkg.core import Migrator, AutoConfig


def colored(text: str, color: str) -> str:
    colors = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m", "blue": "\033[94m", "reset": "\033[0m"}
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def find_migrations() -> Path:
    migrations = AutoConfig.find_migrations_dir()
    if migrations:
        return migrations
    return Path("migrations")


def get_db_url() -> str:
    return AutoConfig.get_database_url() or "sqlite:///app.db"


def cmd_init(args: argparse.Namespace) -> int:
    migrations_dir = Path(args.directory)
    migrations_dir.mkdir(parents=True, exist_ok=True)
    
    print(colored(f"✓", "green"), f"Migrations directory: {migrations_dir}")
    
    db_url = get_db_url()
    print(colored(f"✓", "green"), f"Database: {db_url}")
    
    with Migrator(migrations_dir=migrations_dir) as migrator:
        print(colored(f"✓", "green"), "Migration table created")
    
    print(f"\nReady! Create migrations with: {colored('migrate create <name>', 'blue')}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    name = args.name.lower().replace(" ", "_").replace("-", "_")
    
    if not args.quiet:
        print(f"Creating migration: {colored(name, 'blue')}")
    
    with Migrator() as migrator:
        up_file, down_file = migrator.create_migration(name)
        
    print(colored(f"✓", "green"), f"Created: {up_file.name}")
    print(f"  Edit: {colored(str(up_file), 'yellow')}")
    
    if not args.no_edit:
        editor = os.environ.get("EDITOR", "code")
        os.system(f"{editor} {up_file} {down_file} 2>/dev/null &")
    
    return 0


def cmd_up(args: argparse.Namespace) -> int:
    with Migrator() as migrator:
        errors = migrator.validate()
        if errors:
            print(colored("⚠ Validation errors:", "yellow"))
            for err in errors:
                print(f"  - {err}")
            if not args.force:
                return 1
        
        pending = migrator.get_pending_migrations()
        if not pending:
            print(colored("✓", "green"), "No pending migrations")
            return 0
        
        if not args.quiet:
            print(f"Pending: {len(pending)} migration(s)")
            for m in pending:
                status = " [APPLIED]" if m.status.value == "applied" else ""
                print(f"  - {m.full_name}{status}")
        
        if args.dry_run:
            migrator.migrate_up(steps=args.steps, dry_run=True)
            return 0
        
        if not args.yes:
            response = input(f"\nApply {len(pending) if args.steps < 0 else min(args.steps, len(pending))} migration(s)? [y/N] ")
            if response.lower() not in ("y", "yes"):
                print("Cancelled")
                return 1
        
        applied = migrator.migrate_up(steps=args.steps)
        
        for m in applied:
            print(colored(f"✓", "green"), f"Applied: {m.full_name}")
    
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    with Migrator() as migrator:
        applied = migrator.get_applied_migrations()
        if not applied:
            print(colored("✓", "green"), "No migrations to rollback")
            return 0
        
        if not args.quiet:
            print(f"Will rollback: {len(applied[:args.steps])} migration(s)")
            for m in applied[:args.steps]:
                print(f"  - {m.full_name}")
        
        if args.dry_run:
            migrator.migrate_down(steps=args.steps, dry_run=True)
            return 0
        
        if not args.yes:
            response = input(f"\nRollback {len(applied[:args.steps])} migration(s)? [y/N] ")
            if response.lower() not in ("y", "yes"):
                print("Cancelled")
                return 1
        
        rolled = migrator.migrate_down(steps=args.steps)
        
        for m in rolled:
            print(colored(f"↺", "yellow"), f"Rolled back: {m.full_name}")
    
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    with Migrator() as migrator:
        for migration, status in migrator.status():
            color = "green" if status == "APPLIED" else "yellow" if status == "PENDING" else "red"
            print(f"[{colored(status, color):8}] {migration.full_name}")
    
    return 0


def cmd_fresh(args: argparse.Namespace) -> int:
    with Migrator() as migrator:
        applied = migrator.get_applied_migrations()
        
        if not applied:
            print(colored("✓", "green"), "Already fresh")
            return 0
        
        print(f"Rolling back {len(applied)} migration(s)...")
        
        for m in reversed(applied):
            migrator.migrate_down(steps=1)
            print(colored(f"↺", "yellow"), f"Rolled back: {m.full_name}")
    
    print(colored(f"✓", "green"), "Database is fresh. Run 'migrate up' to reapply.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Database migrations made simple",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    p_init = subparsers.add_parser("init", help="Initialize migrations directory")
    p_init.add_argument("-d", "--directory", default="migrations", help="Directory for migrations")
    p_init.set_defaults(func=cmd_init)

    p_create = subparsers.add_parser("create", help="Create a new migration")
    p_create.add_argument("name", help="Migration name (e.g., add_users_table)")
    p_create.add_argument("-q", "--quiet", action="store_true", help="Minimal output")
    p_create.add_argument("--no-edit", action="store_true", help="Don't open editor")
    p_create.set_defaults(func=cmd_create)

    p_up = subparsers.add_parser("up", help="Apply pending migrations")
    p_up.add_argument("-n", type=int, default=-1, help="Number of migrations (default: all)")
    p_up.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    p_up.add_argument("--dry-run", action="store_true", help="Show what would be done")
    p_up.add_argument("-f", "--force", action="store_true", help="Skip validation")
    p_up.set_defaults(func=cmd_up)

    p_down = subparsers.add_parser("down", help="Rollback last migration")
    p_down.add_argument("-n", "--steps", type=int, default=1, help="Number of migrations")
    p_down.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    p_down.add_argument("--dry-run", action="store_true", help="Show what would be done")
    p_down.set_defaults(func=cmd_down)

    p_status = subparsers.add_parser("status", help="Show migration status")
    p_status.set_defaults(func=cmd_status)

    p_fresh = subparsers.add_parser("fresh", help="Rollback all and re-migrate")
    p_fresh.add_argument("-y", "--yes", action="store_true", help="Skip confirmation")
    p_fresh.set_defaults(func=cmd_fresh)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except Exception as e:
        print(colored(f"✗ Error: {e}", "red"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
