import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from migrate_pkg.drivers.base import BaseDriver

SCHEMA_INIT = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
"""


class SQLiteDriver(BaseDriver):
    def __init__(self, config: str | Path | dict[str, Any]) -> None:
        if isinstance(config, (str, Path)):
            self.db_path = Path(config)
        elif isinstance(config, dict):
            self.db_path = Path(config["database"].replace("sqlite:///", ""))
        else:
            raise ValueError("Invalid config type")

        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str) -> None:
        if not self._conn:
            raise RuntimeError("Not connected")
        self._conn.executescript(sql)
        self._conn.commit()

    def execute_many(self, sql: str, params: tuple) -> None:
        if not self._conn:
            raise RuntimeError("Not connected")
        self._conn.execute(sql, params)
        self._conn.commit()

    def execute_no_commit(self, sql: str) -> None:
        if not self._conn:
            raise RuntimeError("Not connected")
        self._conn.executescript(sql)

    def query(self, sql: str) -> list[dict[str, Any]]:
        if not self._conn:
            raise RuntimeError("Not connected")
        cursor = self._conn.execute(sql)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def init_schema(self) -> None:
        self.execute(SCHEMA_INIT)

    def get_applied_migrations(self) -> list[str]:
        rows = self.query("SELECT version FROM schema_migrations ORDER BY version")
        return [row["version"] for row in rows]

    def record_migration(self, version: str, name: str) -> None:
        applied_at = datetime.utcnow().isoformat()
        self.execute_many(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (version, name, applied_at),
        )

    def remove_migration(self, version: str) -> None:
        self.execute_many("DELETE FROM schema_migrations WHERE version = ?", (version,))
