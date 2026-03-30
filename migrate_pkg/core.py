import os
import re
from pathlib import Path
from typing import Any, Iterator

from migrate_pkg.drivers.base import BaseDriver
from migrate_pkg.models import Migration, MigrationStatus

MIGRATION_PATTERN = re.compile(r"^(\d{3,})_(.+)\.(up|down)\.sql$")


class AutoConfig:
    @staticmethod
    def get_database_url() -> str | None:
        url = os.environ.get("DATABASE_URL")
        if url:
            return url
        
        url_file = Path("DATABASE_URL")
        if url_file.exists():
            return url_file.read_text().strip()
        
        db_file = Path("app.db")
        if db_file.exists():
            return "sqlite:///app.db"
        
        return None

    @staticmethod
    def find_migrations_dir() -> Path | None:
        candidates = [
            Path("migrations"),
            Path("db/migrations"),
            Path("sql/migrations"),
            Path("./"),
        ]
        
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                sql_files = list(candidate.glob("*.sql"))
                if sql_files:
                    return candidate
        
        for candidate in candidates:
            if candidate.exists() and any(candidate.glob("*.sql")):
                return candidate
        
        return Path("migrations")

    @staticmethod
    def detect_driver(url: str) -> str:
        if not url:
            return "sqlite"
        if "postgresql" in url or "postgres" in url:
            return "postgres"
        if "mysql" in url:
            return "mysql"
        return "sqlite"


class Config:
    def __init__(self, database_url: str | None = None, migrations_dir: Path | None = None) -> None:
        self.database_url = database_url or AutoConfig.get_database_url() or "sqlite:///app.db"
        self.migrations_dir = migrations_dir or AutoConfig.find_migrations_dir() or Path("migrations")
        self.driver_type = AutoConfig.detect_driver(self.database_url)


class Migrator:
    def __init__(
        self,
        driver: BaseDriver | None = None,
        migrations_dir: str | Path = "migrations",
        config: Config | None = None,
    ) -> None:
        self.config = config or Config(migrations_dir=Path(migrations_dir))
        
        if driver:
            self.driver = driver
        else:
            from migrate_pkg.drivers import SQLiteDriver, PostgreSQLDriver, MySQLDriver
            
            if self.config.driver_type == "postgres":
                self.driver = PostgreSQLDriver(self._parse_pg_url(self.config.database_url))
            elif self.config.driver_type == "mysql":
                self.driver = MySQLDriver(self._parse_mysql_url(self.config.database_url))
            else:
                self.driver = SQLiteDriver(self.config.database_url)

        self.migrations_dir = Path(self.config.migrations_dir)
        self._migrations: list[Migration] = []

    def _parse_pg_url(self, url: str) -> dict[str, Any]:
        import re
        match = re.match(r"postgresql://(?:(\w+):(\w+)@)?([^:]+):(\d+)?/(.+)", url)
        if match:
            user, password, host, port, db = match.groups()
            return {
                "user": user or "postgres",
                "password": password or "",
                "host": host or "localhost",
                "port": int(port) if port else 5432,
                "database": db or "postgres",
            }
        return {"database": url.replace("postgresql://", "")}

    def _parse_mysql_url(self, url: str) -> dict[str, Any]:
        import re
        match = re.match(r"mysql://(?:(\w+):(\w+)@)?([^:]+):(\d+)?/(.+)", url)
        if match:
            user, password, host, port, db = match.groups()
            return {
                "user": user or "root",
                "password": password or "",
                "host": host or "localhost",
                "port": int(port) if port else 3306,
                "database": db or "mysql",
            }
        return {"database": url.replace("mysql://", "")}

    def init(self) -> None:
        self.driver.connect()
        self.driver.init_schema()
        self._load_migrations()

    def close(self) -> None:
        self.driver.disconnect()

    def __enter__(self) -> "Migrator":
        self.init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _load_migrations(self) -> None:
        self.migrations_dir.mkdir(parents=True, exist_ok=True)

        migrations: dict[str, dict[str, str]] = {}

        for file in sorted(self.migrations_dir.glob("*.sql")):
            match = MIGRATION_PATTERN.match(file.name)
            if not match:
                continue

            version, name, direction = match.groups()
            key = f"{version}_{name}"

            if key not in migrations:
                migrations[key] = {"version": version, "name": name}

            content = file.read_text()
            if direction == "up":
                migrations[key]["up_sql"] = content
            else:
                migrations[key]["down_sql"] = content

        applied = set(self.driver.get_applied_migrations())

        self._migrations = []
        for key, data in sorted(migrations.items(), key=lambda x: x[0]):
            migration = Migration(
                version=data["version"],
                name=data["name"],
                up_sql=data.get("up_sql", ""),
                down_sql=data.get("down_sql", ""),
                status=MigrationStatus.APPLIED if key in applied else MigrationStatus.PENDING,
            )
            self._migrations.append(migration)

    def validate(self) -> list[str]:
        errors: list[str] = []
        for m in self._migrations:
            if not m.up_sql.strip():
                errors.append(f"{m.full_name}: missing .up.sql content")
            if not m.down_sql.strip():
                errors.append(f"{m.full_name}: missing .down.sql content")
            if m.up_sql.strip() and not m.up_sql.strip().endswith(";"):
                errors.append(f"{m.full_name}: .up.sql should end with ';'")
        return errors

    def get_pending_migrations(self) -> list[Migration]:
        return [m for m in self._migrations if m.status == MigrationStatus.PENDING]

    def get_applied_migrations(self) -> list[Migration]:
        return [m for m in self._migrations if m.status == MigrationStatus.APPLIED]

    def migrate_up(self, steps: int = -1, dry_run: bool = False) -> list[Migration]:
        applied: list[Migration] = []
        pending = self.get_pending_migrations()

        for migration in (pending if steps < 0 else pending[:steps]):
            try:
                if dry_run:
                    print(f"  [DRY-RUN] Would apply: {migration.full_name}")
                    continue
                self.driver.execute_no_commit(migration.up_sql)
                self.driver.record_migration(migration.version, migration.name)
                if hasattr(self.driver, "_conn") and self.driver._conn:
                    self.driver._conn.commit()
                migration.status = MigrationStatus.APPLIED
                applied.append(migration)
            except Exception as e:
                if hasattr(self.driver, "_conn") and self.driver._conn:
                    self.driver._conn.rollback()
                migration.status = MigrationStatus.FAILED
                raise RuntimeError(f"Failed: {migration.full_name}: {e}") from e

        return applied

    def migrate_down(self, steps: int = 1, dry_run: bool = False) -> list[Migration]:
        rolled_back: list[Migration] = []
        applied = list(reversed(self.get_applied_migrations()))

        for migration in applied[:steps]:
            try:
                if dry_run:
                    print(f"  [DRY-RUN] Would rollback: {migration.full_name}")
                    continue
                if migration.down_sql:
                    self.driver.execute_no_commit(migration.down_sql)
                self.driver.remove_migration(migration.version)
                self.driver._conn.commit() if hasattr(self.driver, "_conn") and self.driver._conn else None
                migration.status = MigrationStatus.PENDING
                rolled_back.append(migration)
            except Exception as e:
                self.driver._conn.rollback() if hasattr(self.driver, "_conn") and self.driver._conn else None
                raise RuntimeError(f"Failed: {migration.full_name}: {e}") from e

        return rolled_back

    def status(self) -> Iterator[tuple[Migration, str]]:
        for migration in self._migrations:
            yield migration, migration.status.value.upper()

    def create_migration(self, name: str) -> tuple[Path, Path]:
        version = len(self._migrations) + 1
        version_str = str(version).zfill(3)

        up_file = self.migrations_dir / f"{version_str}_{name}.up.sql"
        down_file = self.migrations_dir / f"{version_str}_{name}.down.sql"

        if up_file.exists() or down_file.exists():
            raise FileExistsError(f"Migration already exists: {version_str}_{name}")

        up_file.write_text(f"-- Migration: {name}\n-- Version: {version_str}\n\n")
        down_file.write_text(f"-- Rollback: {name}\n-- Version: {version_str}\n\n")

        return up_file, down_file
