# habits

A local-first terminal app for tracking daily habits. Ticking something off takes one key press, and the daily review is quick. It's encouraging by design: there are no streaks, nothing turns red, and nothing tells you that you "missed" a day.

```
Saturday, 14 November
4 of 10 today

[x] Read
💧 Water ▪▪▪□□□□□ 3/8
[ ] Stretch
```

- **Daily yes/no habits.** For things you do several times a day, a **group** like `💧 Water x8` shows up as one row of boxes.
- **Days start at 5:00 AM**, so ticking something off at 1am still counts for the day you're finishing.
- **Review screen** with yesterday's results, the last 7 days, and a 12-week heatmap where partial days still show up.
- **Your data stays local** in a single SQLite file.

## Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). uv installs Python 3.12+ for you if it's missing.

```sh
uv tool install git+https://github.com/JerryYang42/daily-habit-tickr
habits
```

From a clone:

```sh
git clone https://github.com/JerryYang42/daily-habit-tickr
cd daily-habit-tickr
uv tool install .
habits
```

To upgrade, run `uv tool upgrade habits`. To remove it, run `uv tool uninstall habits` (your data file stays where it is).

## Using it

Press `a` and type a name to add a habit. Type `Name x8` (2 to 50) to make a group, optionally with a leading emoji: `💧 Water x8`.

On a plain habit, `space` toggles it. On a group, `space` ticks the next empty box and `backspace` clears the last ticked one, so you never have to pick a box. After a habit (or a whole group) is done, the cursor moves to the next row.

Every tick counts toward the progress line: Water 3/8 plus one of two other habits reads `4 of 10 today`.

There are no confirmation dialogs. Archiving is undoable instead: `d` archives a row and `u` brings it back. Archived habits keep their history.

### Keys

Vim keys and arrow keys both work. The footer always shows the keys you can use on the current screen.

| Key | Action |
|---|---|
| `j` / `↓`, `k` / `↑` | Move the cursor |
| `g` / `G` | First / last row |
| `space`, `enter` | Toggle a habit, or tick the next box in a group |
| `backspace` | Clear the last ticked box (or un-tick a habit) |
| `a` | Add a habit or group (`Name x8` makes a group) |
| `e` | Rename |
| `d` | Archive |
| `u` | Undo the last archive |
| `+` / `-` | Grow / shrink a group (2 to 50 boxes) |
| `J` / `K` | Move a row down / up |
| `tab` | Switch between Today and Review |
| `?` | Help |
| `q` | Quit |

### How days work

- Your day changes at **5:00 AM local time**. If the app is open at that moment, it switches to the new day by itself.
- You can only tick things off for **today**. Once a day ends, it's read-only.
- Each tick is saved with the day it belongs to, so changing time zones or clocks later never rewrites your history.
- When a group grows or shrinks, earlier days keep their old size. A habit added today doesn't show up on earlier days.

## Your data

Everything is in one SQLite file:

| OS | Default database path |
|---|---|
| macOS | `~/Library/Application Support/habits/habits.db` |
| Linux | `~/.local/share/habits/habits.db` (or `$XDG_DATA_HOME/habits/habits.db`) |
| Windows | `%LOCALAPPDATA%\habits\habits.db` |

Run `habits --where` to print the exact paths on your machine. To use a different file, pass `--db PATH` or set `HABITS_DB`.

The schema already has what sync would need (UUIDv7 IDs, `updated_at`, `device_id`, and un-ticks stored as tombstones rather than deleted rows), but sync itself isn't built yet. See [ROADMAP.md](ROADMAP.md).

## Config

The config file is optional; without one, the defaults apply. It lives in the user config directory: `~/.config/habits/config.toml` on Linux and `~/Library/Application Support/habits/config.toml` on macOS. Run `habits --where` to see the path, or pass `--config PATH` or set `HABITS_CONFIG` to use a different one.

```toml
# Hour (0-23) when a new day starts. Default: 5
day_start_hour = 5

# IANA time zone. Default: your system's local time
timezone = "Europe/London"
```

## Development

```sh
uv sync                    # create .venv with dev tools
uv run habits              # run from source
uv run pytest              # tests (core, db, Textual Pilot, snapshots)
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy                # types (strict)
```

If you change the UI on purpose, update the snapshots with `uv run pytest tests/ui/test_snapshots.py --snapshot-update` and look over the report before you commit.

The code is split into three layers: `ui → core ← db`. `habits.core` is plain Python with no Textual or SQLite imports, and `tests/test_layering.py` checks that. See [PLAN.md](PLAN.md) for the design.

Schema changes go in a new numbered file under `src/habits/db/migrations/` (`0002_*.sql`, and so on). Migrations only move forward, each one runs in a single transaction, and the app refuses to open a database that's newer than it understands.
