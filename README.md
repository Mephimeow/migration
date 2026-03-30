# dbmigrate

Простой инструмент для миграций баз данных. Минимум конфигурации — максимум результата.

## Возможности

**Автоопределение** - Автоматически находит БД и папку с миграциями 
**Транзакции** - Безопасные миграции с откатом при ошибках 
**Валидация** - Проверка SQL перед применением 
**Dry-run** - Просмотр что будет сделано 
**Multi-DB** - PostgreSQL, MySQL, SQLite 
**Rollback** - Откат отдельных или всех миграций 

## Установка

```bash
pip install dbmigrate
pip install dbmigrate[postgres]   # PostgreSQL
pip install dbmigrate[mysql]       # MySQL
pip install dbmigrate[all-db]     # Все драйверы
```

## Быстрый старт

```bash
# 1. Инициализация (создаёт папку migrations и таблицу миграций)
migrate init

# 2. Создать миграцию (откроет редактор)
migrate create add_users

# 3. Применить миграции
migrate up

# 4. Проверить статус
migrate status
```

## Команды CLI

### `migrate init` — Инициализация

Создаёт папку с миграциями и таблицу `schema_migrations` в БД.

```bash
migrate init                    # По умолчанию: ./migrations, sqlite://app.db
migrate init -d ./db/migrations # Кастомная папка
migrate init sqlite:///prod.db  # Кастомная БД
```

**Автоопределение:**
- DATABASE_URL из переменной окружения
- Файл `DATABASE_URL` в проекте
- Существующий `app.db` → SQLite
- Папка `migrations/`, `db/migrations/` или `sql/migrations/`

### `migrate create` — Создать миграцию

Создаёт пару файлов `.up.sql` и `.down.sql`.

```bash
migrate create add_users_table
migrate create create_posts_table
```

**Результат:**
```
migrations/
├── 001_add_users_table.up.sql
└── 001_add_users_table.down.sql
```

**Опции:**
```bash
migrate create add_users --no-edit    # Не открывать редактор
migrate create add_users -q           # Минимальный вывод
```

### `migrate up` — Применить миграции

Применяет все ожидающие миграции.

```bash
migrate up                  # Все миграции
migrate up -n 2             # Только 2 миграции
migrate up --dry-run        # Показать что будет
migrate up -y               # Без подтверждения
migrate up -f               # Пропустить валидацию
```

**Dry-run вывод:**
```
[DRY-RUN] Would apply: 001_add_users
[DRY-RUN] Would apply: 002_create_posts
```

### `migrate down` — Откатить миграции

Откатывает последние применённые миграции.

```bash
migrate down                # Откатить 1 миграцию
migrate down -n 3           # Откатить 3 миграции
migrate down --dry-run      # Показать что будет
migrate down -y             # Без подтверждения
```

### `migrate status` — Статус миграций

Показывает состояние всех миграций.

```bash
migrate status
```

**Вывод:**
```
[APPLIED ] 001_add_users_table
[PENDING ] 002_create_posts
[APPLIED ] 003_add_comments
```

### `migrate fresh` — Полный сброс

Откатывает все миграции (для development).

```bash
migrate fresh              # С подтверждением
migrate fresh -y          # Без подтверждения
```

## Формат миграций

Каждая миграция состоит из двух файлов:

### `XXX_name.up.sql` — Применение

```sql
-- Миграция: add_users
-- Версия: 001

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
```

### `XXX_name.down.sql` — Откат

```sql
-- Откат: add_users
-- Версия: 001

DROP TABLE IF EXISTS users;
```

## Конфигурация

### Автоматическая (по умолчанию)

Инструмент автоматически ищет:

1. `DATABASE_URL` — переменная окружения
2. Файл `DATABASE_URL` — содержит URL базы
3. `app.db` — SQLite база в проекте
4. Папка `migrations/`

### Ручная через `migrate.toml`

```toml
[migration]
directory = "migrations"
database = "postgresql://user:pass@localhost:5432/mydb"
```

### Поддерживаемые URL

```
sqlite:///app.db
sqlite:///var/data/app.db
postgresql://user:pass@localhost:5432/mydb
postgresql://user:pass@host/mydb
mysql://user:pass@localhost:3306/mydb
```

## Библиотека (Python API)

### Базовое использование

```python
from migrate_pkg import Migrator
from migrate_pkg.drivers import SQLiteDriver

with Migrator() as migrator:
    migrator.migrate_up()
```

### С указанием драйвера

```python
from migrate_pkg import Migrator
from migrate_pkg.drivers import PostgreSQLDriver

driver = PostgreSQLDriver({
    "host": "localhost",
    "port": 5432,
    "database": "mydb",
    "user": "user",
    "password": "pass"
})

migrator = Migrator(driver, "migrations")
migrator.init()

# Применить все
applied = migrator.migrate_up()

# Применить 2 миграции
applied = migrator.migrate_up(steps=2)

# Откатить 1
rolled = migrator.migrate_down()

# Статус
for migration, status in migrator.status():
    print(f"[{status}] {migration.full_name}")

migrator.close()
```

### Программное создание миграции

```python
with Migrator() as migrator:
    up_file, down_file = migrator.create_migration("add_products")
    up_file.write_text("CREATE TABLE products (...)")
    down_file.write_text("DROP TABLE products")
```

### Валидация

```python
with Migrator() as migrator:
    errors = migrator.validate()
    if errors:
        for err in errors:
            print(f"⚠ {err}")
```

## Безопасность

- **Транзакции**: миграция выполняется атомарно
- **SQL-инъекции**: параметризованные запросы
- **Валидация**: проверка .down.sql перед применением
- **Dry-run**: предпросмотр перед изменениями
- **Подтверждения**: интерактивный запрос перед опасными действиями

## License

MIT
