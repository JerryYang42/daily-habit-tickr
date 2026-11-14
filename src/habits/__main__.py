"""Entry point: ``habits`` (or ``python -m habits``)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    from habits import __version__

    p = argparse.ArgumentParser(prog="habits", description="A gentle daily habit tracker.")
    p.add_argument("--db", type=Path, help="database file (default: user data dir, or $HABITS_DB)")
    p.add_argument("--config", type=Path, help="config file (default: user config dir)")
    p.add_argument("--where", action="store_true", help="print data and config paths, then exit")
    p.add_argument("--version", action="version", version=f"habits {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Keep imports lazy so `--version` and `--help` stay instant.
    from habits.config import ConfigError, default_config_path, load_config
    from habits.db.connection import NewerSchemaError, connect, default_db_path

    env_db = os.environ.get("HABITS_DB")
    db_path: Path = args.db or (Path(env_db) if env_db else default_db_path())
    config_path: Path = args.config or default_config_path()

    if args.where:
        print(f"database: {db_path}")
        print(f"config:   {config_path}")
        return 0

    try:
        config = load_config(config_path)
        conn = connect(db_path)
    except (ConfigError, NewerSchemaError) as e:
        print(f"habits: {e}", file=sys.stderr)
        return 2

    from habits.core.clock import SystemClock
    from habits.core.service import HabitService
    from habits.db.repo import SqliteRepository
    from habits.ui.app import HabitsApp

    try:
        service = HabitService(
            SqliteRepository(conn),
            SystemClock(config.timezone),
            day_start_hour=config.day_start_hour,
        )
        HabitsApp(service).run()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
