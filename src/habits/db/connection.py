"""Open the database: path, pragmas, migrations, device id."""

from __future__ import annotations

import re
import sqlite3
from importlib import resources
from pathlib import Path

from habits.core.ids import new_id

APP_NAME = "habits"
_MIGRATION_RE = re.compile(r"^(\d{4})_.+\.sql$")


class NewerSchemaError(RuntimeError):
    """The database was written by a newer version of the app."""


def default_db_path() -> Path:
    from platformdirs import user_data_path

    return user_data_path(APP_NAME, appauthor=False) / "habits.db"


def migrations() -> list[tuple[int, str]]:
    """(version, sql) pairs, sorted by version."""
    found: list[tuple[int, str]] = []
    for entry in resources.files("habits.db.migrations").iterdir():
        m = _MIGRATION_RE.match(entry.name)
        if m:
            found.append((int(m.group(1)), entry.read_text(encoding="utf-8")))
    found.sort()
    versions = [v for v, _ in found]
    if versions != list(range(1, len(versions) + 1)):
        raise RuntimeError(f"migrations must be numbered 1..N without gaps, got {versions}")
    return found


def latest_version() -> int:
    return len(migrations())


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations, each in its own transaction. Returns the final version."""
    current: int = conn.execute("PRAGMA user_version").fetchone()[0]
    steps = migrations()
    latest = len(steps)
    if current > latest:
        raise NewerSchemaError(
            f"database schema v{current} is newer than this app understands (v{latest})"
        )
    for version, sql in steps:
        if version <= current:
            continue
        try:
            conn.execute("BEGIN")
            for statement in _split_sql(sql):
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {version:d}")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        current = version
    return current


def _split_sql(sql: str) -> list[str]:
    """Split a migration into statements (migrations contain no triggers or string ';')."""
    lines = [ln for ln in sql.splitlines() if not ln.lstrip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def ensure_device_id(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM meta WHERE key = 'device_id'").fetchone()
    if row:
        return str(row[0])
    device_id = new_id()
    conn.execute("INSERT INTO meta (key, value) VALUES ('device_id', ?)", (device_id,))
    return device_id


def connect(path: str | Path) -> sqlite3.Connection:
    """Open (creating if needed) and migrate a database. Use ':memory:' for tests."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None)  # explicit transactions only
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        migrate(conn)
        ensure_device_id(conn)
    except BaseException:
        conn.close()
        raise
    return conn
