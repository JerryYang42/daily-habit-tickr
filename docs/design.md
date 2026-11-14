# Design

How `habits` works and why. This describes the code as it is. When behavior changes, update this file in the same PR.

- Usage and install: [README.md](../README.md)
- What's next: [ROADMAP.md](../ROADMAP.md)
- What shipped when: [CHANGELOG.md](../CHANGELOG.md)

## 1. Goals and non-goals

`habits` is a local-first terminal app for tracking daily habits. Ticking something off should take one key press, and the daily review should be quick. It's encouraging by design and never punishes or shames.

**Goals**
- Add habits, and mark a habit done or not done before the logical day ends.
- The logical day ends at **5:00 AM local time**.
- Encouraging tone throughout.
- Fast startup, keyboard-first, easy navigation.
- SQLite storage, local-first, with a schema that's ready for sync (sync itself isn't built).

**Non-goals**
- Streaks of any kind.
- Backfilling past days. After the 5am rollover, the previous day is read-only.
- Non-daily schedules (weekly, Mon/Wed/Fri) and numeric habits. Habits are daily yes/no only. Things you do several times a day (8 glasses of water) are **groups** (section 5.2).
- Anything listed in [ROADMAP.md](../ROADMAP.md) until someone asks for it.

## 2. Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12+ (CI runs 3.12, 3.13 and 3.14) |
| TUI | [Textual](https://textual.textualize.io/) |
| Storage | stdlib `sqlite3` behind a thin repository. No ORM. |
| Packaging | `uv` with a `hatchling` build backend |
| Lint, format, types | `ruff`, `ruff format`, `mypy --strict` |
| Tests | `pytest`, `pytest-asyncio`, `pytest-textual-snapshot` |
| Paths | `platformdirs` |
| Time zones | stdlib `zoneinfo` |
| Config | TOML via stdlib `tomllib` (optional file, read-only) |
| IDs | UUIDv7: stdlib `uuid.uuid7` on 3.14+, otherwise the `uuid-utils` package |
| Migrations | Hand-rolled numbered SQL files, tracked with `PRAGMA user_version` |

## 3. Core concepts

### 3.1 Logical day (the 5am rule)

- `logical_day(now_local, day_start_hour=5) = (wall_clock(now_local) - timedelta(hours=day_start_hour)).date()`. The time zone is removed before subtracting, so a DST change never moves the boundary.
- At 02:00 on Tuesday, the logical day is Monday. At 05:00 Tuesday, it becomes Tuesday.
- Logical days are stored as `YYYY-MM-DD` text and **computed once, when the row is written**. They're never recomputed from timestamps, so DST changes and travel can't rewrite history.
- Where `day_start_hour` comes from, highest priority first: the TOML config, then the `settings` table, then the default of 5.
- The clock is **injected**. The service takes a `Clock` (anything with `now() -> aware datetime`): `SystemClock` in the app, `ManualClock` in tests.
- The service only ever **writes** to the current logical day. Past days are read-only.

### 3.2 Done, not done, and tombstones

- Marking a habit done upserts `completions(habit_id, day)` with `state='done'`.
- Un-ticking sets `state='cleared'`, a tombstone. **Rows are never deleted**, which keeps the schema ready for sync. Queries treat `cleared` the same as no row.
- Every write sets `updated_at` (UTC ISO-8601 with microseconds) and `device_id`.

### 3.3 Habit lifetime

- Habits and groups have a `created_day` and an optional `archived_day`, both logical days stored as text.
- An item is **active on day D** if `created_day <= D` and (`archived_day IS NULL` or `archived_day > D`).
- Days before a habit existed are blank, never "missed".
- Items are archived, never deleted. History is never lost.
- Because `archived_day` is exclusive, **an item archived today disappears from today**, along with any ticks it had today. Earlier days are unaffected.

## 4. Data model

The schema lives in [`0001_init.sql`](../src/habits/db/migrations/0001_init.sql) (`user_version = 1`):

```sql
CREATE TABLE meta     (key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- device_id
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- day_start_hour = '5'

CREATE TABLE habit_groups (
  id TEXT PRIMARY KEY,              -- UUIDv7
  name TEXT NOT NULL,
  emoji TEXT,
  sort_key TEXT NOT NULL,           -- fractional key (section 4.1)
  created_day TEXT NOT NULL,
  archived_day TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE habits (
  id TEXT PRIMARY KEY,              -- UUIDv7
  name TEXT NOT NULL,
  sort_key TEXT NOT NULL,
  group_id TEXT REFERENCES habit_groups(id),  -- NULL for plain habits
  group_pos INTEGER,                          -- position inside a group, NULL otherwise
  created_day TEXT NOT NULL,
  archived_day TEXT,
  updated_at TEXT NOT NULL,
  CHECK ((group_id IS NULL) = (group_pos IS NULL))
);

CREATE TABLE completions (
  habit_id TEXT NOT NULL REFERENCES habits(id),
  day TEXT NOT NULL,                -- logical day, YYYY-MM-DD
  state TEXT NOT NULL CHECK (state IN ('done','cleared')),
  updated_at TEXT NOT NULL,         -- UTC
  device_id TEXT NOT NULL,          -- UUIDv7, generated on first run
  PRIMARY KEY (habit_id, day)
);

CREATE INDEX idx_completions_day ON completions(day);
CREATE INDEX idx_habits_group ON habits(group_id, group_pos);
```

Notes:
- A **group** is a set of ordinary `habits` rows (members) that share a `group_id`. Completions, history and future sync therefore work the same for members as for plain habits. Groups only add a display and behavior layer on top.
- Members copy the group's `name` (renaming a group renames its members) and its `sort_key`. They never appear in the list on their own.
- Plain habits and groups share one ordering: the Today list mixes them, sorted by `(sort_key, id)`.
- `group_pos` is 1..N when a group is created. Later growth always uses *highest position ever used + 1* (section 5.2), so the positions of active members can have gaps.

### 4.1 Sort keys

`sort_key` is a fractional, lexicographic key ([`core/sortkeys.py`](../src/habits/core/sortkeys.py)) made of base-62 ASCII digits, never ending in `0`. `key_between(a, b)` always finds a key strictly between two others. Appending steps up by one digit, so keys stay short for lists built mostly by adding rows at the end.

Moving a row rewrites **only that row's key**, which keeps reorders cheap and limits sync conflicts to one row. If two keys ever collide (for example, after a future sync), the visible rows are renumbered in one transaction.

## 5. Behavior

### 5.1 Plain habit

- `space` / `enter` toggles done ↔ not done for today. `backspace` un-ticks it.
- It's shown as `[x] Read` / `[ ] Read`.
- When a toggle marks a habit done, the cursor moves to the next row. Un-ticking leaves the cursor where it is.
- Emoji aren't treated specially for plain habits. `📚 Read` is just the name.

### 5.2 Group

- `Name x8` in the add prompt creates a group and 8 members in **one transaction**. `X`, `×` and `x 8` (with a space) also work. A leading emoji is stored separately (`💧 Water x8`). Counts must be 2 to 50; anything else is treated as a plain habit name.
- It's shown as one row: `💧 Water ▪▪▪□□□□□ 3/8`.
- **Tick** (`space` / `enter`) marks the lowest-position active member that isn't done today as done. When every box is ticked, nothing happens (no wrap-around, no error).
- **Clear last** (`backspace`) clears the highest-position member that's done today.
- The user never picks a box. Ticks always fill from the left, so the done boxes are always the first ones.
- The cursor moves to the next row only when the group becomes fully done.
- **Resize** (`+` / `-`, shown in the footer only when the cursor is on a group):
  - `+` adds a new member at *highest position ever used + 1*, with `created_day = today`. It never brings back an archived member, because that would change the box count of the days when that member was archived.
  - `-` archives the highest-position active member (`archived_day = today`). If that box was ticked today, the tick goes with it.
  - Size stays between 2 and 50. At either limit the app shows a gentle notice and does nothing.
  - Past days keep their own box counts, because activity is worked out per day (section 3.3).
- **Archive** archives the group and all its active members together. **Undo** restores the group and exactly the members that archive touched. Members removed earlier with `-` stay archived.

### 5.3 Archive and undo

- `d` archives with no confirmation. `u` undoes. The rule is **undoable instead of confirmable**: there are no "are you sure?" dialogs.
- Each archive returns an `ArchiveToken` (kind, id, name, day, member ids). The app keeps an undo stack of these for the current session.
- Undo only works on the day the archive happened. The undo stack is cleared at rollover, and `restore` refuses a token from an earlier day, because undoing it would change a past day.

### 5.4 Progress line

**Each tick counts.** The line shows total ticks over total active habits, and a group of N contributes N. Water 3/8 plus two plain habits with one done reads `4 of 10 today`.
- Partial progress always moves the number up.
- To count each group as a single row instead, set `PROGRESS_MODE = "rows"` in [`core/stats.py`](../src/habits/core/stats.py).
- The copy is neutral or warm: `Fresh day, ready when you are` at zero and `All N done today. Lovely.` when everything is done.

### 5.5 Rollover at 5am

- The app sets a one-shot timer for the next boundary (plus 0.5 s). It also re-checks every 45 s, to cope with suspend/resume and clock changes.
- At the boundary, it reloads the current screen for the new day, clears the undo stack and shows `New day, fresh start ☀️`. The cursor stays on the same row when that row still exists.
- `HabitsApp.check_rollover()` can be called directly, which is how the tests drive it with a `ManualClock`.

### 5.6 Review screen

Read-only. `tab` switches between Today and Review. It has:
1. **Yesterday:** each habit and group with its result (not-done items are just unticked, never red), plus a summary line such as `You did 6 of 9 yesterday`.
2. **This week:** done ticks over active habits for each of the last 7 logical days, **including today**, with a small bar.
3. `You checked something off on X of the last 14 days` (including today).
4. **Heatmap:** the last 12 weeks, one column per week (Monday first), so the last column is the current week and future days are left empty. Each cell is shaded by `done / active`:
   - No habits active that day: blank.
   - Habits active, nothing ticked: a quiet grey.
   - Then four greens: ≤25%, ≤50%, <100%, 100%. A partial day is always visibly something.
   - There are separate palettes for dark and light themes. Neither uses red.

Stats are **positive only**: counts and "X of the last N days". No streaks, no resets, no "days missed".

### 5.7 Keys

The key list lives in the [README](../README.md#keys) and in `messages.HELP_ROWS` (the `?` screen). The rules behind it:
- Vim keys and arrow keys both work. There are no modes.
- The footer shows the keys that apply right now. It uses `check_action` to hide actions that don't fit the current row.

## 6. Code layout

```
src/habits/
  __main__.py          # `habits` entry point; argparse; heavy imports are deferred
  config.py            # optional config.toml (day_start_hour, timezone)
  messages.py          # all user-facing copy
  core/                # pure Python: no textual, sqlite3 or rich imports
    clock.py           # Clock, SystemClock, ManualClock, logical_day, next_boundary
    ids.py             # new_id() -> UUIDv7 string
    models.py          # Habit, HabitGroup, Completion, TodayRow, DayView, ReviewView, ArchiveToken
    parsing.py         # "💧 Water x8" -> ParsedAdd
    service.py         # Repository protocol + HabitService (every use case)
    sortkeys.py        # fractional sort keys
    stats.py           # progress, day totals, heatmap shading
  db/
    connection.py      # connect(): pragmas, migrations, device_id, default path
    repo.py            # SqliteRepository: the only SQL in the app
    migrations/0001_init.sql
  ui/
    app.py             # HabitsApp: modes, undo stack, rollover timers
    styles.tcss
    screens/           # today.py, review.py, help.py
    widgets/           # habit_row.py, group_row.py, heatmap.py, add_prompt.py
tests/
  core/  db/  ui/      # unit tests, service tests on :memory:, Pilot and snapshot tests
  test_layering.py     # enforces the dependency rules below
```

**Dependency rules:** `ui → core ← db`. The UI never touches SQL. Core never imports Textual or `sqlite3`. `HabitService` depends on the `Repository` protocol, so tests run it against in-memory SQLite. `tests/test_layering.py` fails the build if these rules are broken.

**UI notes**
- Screens call `HabitService` and then `reload()`. A reload re-reads the day, updates row widgets in place when the list of row ids hasn't changed, and rebuilds them when it has.
- Reloads hold a lock, because closing a modal fires both the modal's callback and the screen's resume event, and two overlapping reloads would mount every row twice.
- Today and Review are Textual *modes*. The Review screen isn't built until the first `tab`, so startup only loads today's data.

## 7. Engineering practices

- **Testing:**
  - Table-driven tests for `logical_day` (04:59 vs 05:00, midnight, DST spring-forward and fall-back, month, year and leap-day boundaries).
  - Service tests on `:memory:` SQLite with a `ManualClock`.
  - Group tests: tick order, clear-last, resize, archive/restore, and box counts on past days.
  - Pilot tests for the main key flows, including rollover and persistence across restarts.
  - Three SVG snapshots (Today, empty Today, Review).
- **Quality gates** (each must pass before merging; CI runs them on Ubuntu and macOS with Python 3.12–3.14): `ruff check .`, `ruff format --check .`, `mypy`, `pytest`.
- **Migrations:** forward-only numbered files (`NNNN_name.sql`, numbered 1..N with no gaps). Each runs in its own transaction and bumps `user_version`. The app refuses to open a database whose `user_version` is newer than it knows.
- **Data safety:** WAL mode and foreign keys on every connection. Operations that touch several rows (creating, renaming or archiving a group; renumbering) run in one transaction.
- **Performance:** startup should feel instant. `--version`, `--help` and `--where` don't import Textual, and the first screen loads only today's rows.
- **Config:** `config.toml` is optional, and invalid values are rejected with a clear message and exit code 2. Defaults need no file.
- **Commits:** small, one logical change each, conventional commit messages.

## 8. Decisions

| Question | Decision | Why |
|---|---|---|
| Language and UI | Python + Textual | CSS styling, key bindings, a footer, and Pilot for tests |
| Habit types | Daily yes/no only; multi-count via groups | Keeps capture to one key press, and members reuse all the completion and history logic |
| Backfill | None; past days are read-only | Keeps history honest and simple (a gentle backfill is on the roadmap) |
| Streaks | None | Streak resets feel like punishment |
| Sync | Not built; the schema is ready for it | UUIDv7, tombstones, `updated_at` and `device_id` are already in place |
| How a group is shown | One row per group | Keeps the list short |
| Progress line | Each tick counts | Partial progress always shows; switchable in `core/stats.py` |
| Project location | Repo root (not a `habits/` subfolder) | The repo is the project |
| Archive semantics | `archived_day = today`, exclusive | One rule for "active on D" everywhere. Accepted cost: today's ticks on that item stop counting |
| Undo scope | Same logical day only; stack cleared at rollover | Keeps past days read-only |
| Growing after shrinking | New member at highest position + 1; archived members never revived | Keeps the box count of past days correct |
| `backspace` on a plain habit | Un-ticks it | Same meaning as on a group: "clear the last tick" |
| Week and 14-day stats | Include today | Today can only add to them, never take away |
| Reordering | Fractional sort keys | One-row writes; friendlier to future sync |
