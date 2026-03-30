from typing import Any

try:
    import psycopg

    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

from migrate_pkg.drivers.base import BaseDriver

SCHEMA_INIT = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class PostgreSQLDriver(BaseDriver):
    def __init__(self, config: dict[str, Any]) -> None:
        if not HAS_PSYCOPG:
            raise ImportError("psycopg is required: pip install dbmigrate[postgres]")

        self.config = config
        self._conn: psycopg.Connection | None = None

    def _dsn(self) -> str:
        c = self.config
        return (
            f"host={c.get('host', 'localhost')} "
            f"port={c.get('port', 5432)} "
            f"dbname={c.get('database', 'postgres')} "
            f"user={c.get('user', 'postgres')} "
            f"password={c.get('password', '')}"
        )

    def connect(self) -> None:
        self._conn = psycopg.connect(self._dsn())

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute(self, sql: str) -> None:
        if not self._conn:
            raise RuntimeError("Not connected")
        with self._conn.cursor() as cur:
            cur.execute(sql)
        self._conn.commit()

    def execute_many(self, sql: str, params: tuple) -> None:
        if not self._conn:
            raise RuntimeError("Not connected")
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
        self._conn.commit()

    def execute_no_commit(self, sql: str) -> None:
        if not self._conn:
            raise RuntimeError("Not connected")
        with self._conn.cursor() as cur:
            cur.execute(sql)

    def query(self, sql: str) -> list[dict[str, Any]]:
        if not self._conn:
            raise RuntimeError("Not connected")
        with self._conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]

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
