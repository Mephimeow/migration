from typing import Any

try:
    import mysql.connector

    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

from migrate_pkg.drivers.base import BaseDriver

SCHEMA_INIT = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class MySQLDriver(BaseDriver):
    def __init__(self, config: dict[str, Any]) -> None:
        if not HAS_MYSQL:
            raise ImportError(
                "mysql-connector-python is required: pip install dbmigrate[mysql]"
            )

        self.config = config
        self._conn: mysql.connector.MySQLConnection | None = None

    def _get_connection_params(self) -> dict[str, Any]:
        c = self.config
        return {
            "host": c.get("host", "localhost"),
            "port": c.get("port", 3306),
            "database": c.get("database", "mysql"),
            "user": c.get("user", "root"),
            "password": c.get("password", ""),
        }

    def connect(self) -> None:
        self._conn = mysql.connector.connect(**self._get_connection_params())

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str) -> None:
        if not self._conn:
            raise RuntimeError("Not connected")
        cursor = self._conn.cursor()
        for statement in sql.split(";"):
            if statement.strip():
                cursor.execute(statement)
        self._conn.commit()
        cursor.close()

    def execute_many(self, sql: str, params: tuple) -> None:
        if not self._conn:
            raise RuntimeError("Not connected")
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        self._conn.commit()
        cursor.close()

    def execute_no_commit(self, sql: str) -> None:
        if not self._conn:
            raise RuntimeError("Not connected")
        cursor = self._conn.cursor()
        for statement in sql.split(";"):
            if statement.strip():
                cursor.execute(statement)
        cursor.close()

    def query(self, sql: str) -> list[dict[str, Any]]:
        if not self._conn:
            raise RuntimeError("Not connected")
        cursor = self._conn.cursor(dictionary=True)
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def init_schema(self) -> None:
        self.execute(SCHEMA_INIT)

    def get_applied_migrations(self) -> list[str]:
        rows = self.query("SELECT version FROM schema_migrations ORDER BY version")
        return [row["version"] for row in rows]

    def record_migration(self, version: str, name: str) -> None:
        self.execute_many(
            "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
            (version, name),
        )

    def remove_migration(self, version: str) -> None:
        self.execute_many("DELETE FROM schema_migrations WHERE version = %s", (version,))
