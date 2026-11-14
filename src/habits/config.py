"""Optional TOML config. Defaults need no file.

# ~/.config/habits/config.toml (platform dependent)
day_start_hour = 5
timezone = "Europe/London"
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from habits.db.connection import APP_NAME


class ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Config:
    day_start_hour: int | None = None  # None: use the value stored in the database
    timezone: ZoneInfo | None = None  # None: system local time


def default_config_path() -> Path:
    env = os.environ.get("HABITS_CONFIG")
    if env:
        return Path(env)
    from platformdirs import user_config_path

    return user_config_path(APP_NAME, appauthor=False) / "config.toml"


def load_config(path: Path | None = None) -> Config:
    path = path or default_config_path()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return Config()
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise ConfigError(f"{path}: {e}") from e

    hour = data.get("day_start_hour")
    if hour is not None and (
        not isinstance(hour, int) or isinstance(hour, bool) or not 0 <= hour <= 23
    ):
        raise ConfigError(f"{path}: day_start_hour must be an integer 0..23")

    tz_name = data.get("timezone")
    tz: ZoneInfo | None = None
    if tz_name is not None:
        if not isinstance(tz_name, str):
            raise ConfigError(f"{path}: timezone must be a string like 'Europe/London'")
        try:
            tz = ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ConfigError(f"{path}: unknown timezone {tz_name!r}") from e
    return Config(day_start_hour=hour, timezone=tz)
