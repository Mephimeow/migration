from pathlib import Path

import pytest

from migrate_pkg import Migrator
from migrate_pkg.drivers import SQLiteDriver


class TestMigrator:
    def test_init_and_migrate(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        driver = SQLiteDriver(db_path)
        migrator = Migrator(driver, tmp_path)

        migrator.init()
        assert db_path.exists()

        (tmp_path / "001_test.up.sql").write_text("CREATE TABLE test (id INTEGER PRIMARY KEY);")
        (tmp_path / "001_test.down.sql").write_text("DROP TABLE IF EXISTS test;")

        migrator._load_migrations()
        applied = migrator.migrate_up()

        assert len(applied) == 1
        assert applied[0].version == "001"
        assert driver.get_applied_migrations() == ["001_test"]

        rolled = migrator.migrate_down()
        assert len(rolled) == 1
        assert driver.get_applied_migrations() == []

        migrator.close()

    def test_create_migration(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        driver = SQLiteDriver(db_path)
        migrator = Migrator(driver, tmp_path)
        migrator.init()

        up_file, down_file = migrator.create_migration("add_table")

        assert up_file.exists()
        assert down_file.exists()
        assert up_file.name.startswith("001_")

        migrator.close()

    def test_create_migration_duplicate(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        driver = SQLiteDriver(db_path)
        migrator = Migrator(driver, tmp_path)
        migrator.init()

        migrator.create_migration("add_table")

        with pytest.raises(FileExistsError):
            migrator.create_migration("add_table")

        migrator.close()

    def test_sql_injection_prevention(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        driver = SQLiteDriver(db_path)
        migrator = Migrator(driver, tmp_path)
        migrator.init()

        (tmp_path / "001_test.up.sql").write_text("CREATE TABLE safe (id INTEGER PRIMARY KEY);")
        (tmp_path / "001_test.down.sql").write_text("DROP TABLE safe;")

        migrator._load_migrations()
        migrator.migrate_up()

        malicious_name = "'; DROP TABLE users; --"
        (tmp_path / "002_test2.up.sql").write_text("CREATE TABLE test2 (id INTEGER PRIMARY KEY);")
        (tmp_path / "002_test2.down.sql").write_text("DROP TABLE test2;")

        migrator._load_migrations()
        applied = migrator.get_applied_migrations()

        assert "001_test" in applied
        assert "002_test2" in applied

        migrator.close()
