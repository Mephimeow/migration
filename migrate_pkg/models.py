from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class MigrationStatus(Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"


@dataclass
class Migration:
    version: str
    name: str
    up_sql: str
    down_sql: str
    status: MigrationStatus = MigrationStatus.PENDING
    applied_at: datetime | None = None

    @property
    def up_file(self) -> Path:
        return Path(f"{self.version}_{self.name}.up.sql")

    @property
    def down_file(self) -> Path:
        return Path(f"{self.version}_{self.name}.down.sql")

    @property
    def full_name(self) -> str:
        return f"{self.version}_{self.name}"
