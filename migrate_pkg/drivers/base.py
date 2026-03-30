from abc import ABC, abstractmethod
from typing import Any


class BaseDriver(ABC):
    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def execute(self, sql: str) -> None:
        pass

    @abstractmethod
    def execute_many(self, sql: str, params: tuple) -> None:
        pass

    @abstractmethod
    def execute_no_commit(self, sql: str) -> None:
        pass

    @abstractmethod
    def query(self, sql: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def init_schema(self) -> None:
        pass

    @abstractmethod
    def get_applied_migrations(self) -> list[str]:
        pass

    @abstractmethod
    def record_migration(self, version: str, name: str) -> None:
        pass

    @abstractmethod
    def remove_migration(self, version: str) -> None:
        pass
