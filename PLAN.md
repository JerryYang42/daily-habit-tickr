# Habit Tracker TUI: Implementation Plan

A local-first terminal UI for tracking daily habits. Built for instant, no-brainer capture during the day and a quick daily review. Encouraging by design: it never punishes or shames.

Deferred work lives in [ROADMAP.md](ROADMAP.md). Do not implement roadmap items unless asked.

## 1. Goals and non-goals

**Goals**
- Add habits; mark a habit done or cancel it (un-mark) before the logical day ends.
- The logical day ends at **5:00 AM local time**.
- Encouraging tone. Never punish or shame.
- Fast startup, keyboard-first, easy navigation.
- SQLite storage. Local-first. Schema is sync-ready (sync itself is not built).

**Non-goals (for now)**
- Streaks of any kind.
- Backfilling past days. After the 5am rollover the previous day is read-only.
- Non-daily schedules (weekly, Mon/Wed/Fri) or numeric/countable habits. Only daily yes/no. Multi-count things (e.g. 8 glasses of water) are modeled as **groups** (see section 4).
- Categories, sync, export, rich encouragement copy (all in ROADMAP.md).

## 2. Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12+ |
| TUI | [Textual](https://textual.textualize.io/) (CSS styling, key bindings, auto footer, Pilot for tests) |
| Storage | stdlib `sqlite3` with a thin repository layer. No ORM. |
| Project and packaging | `uv` (`pyproject.toml`, `uv tool install`) |
| Lint and format | `ruff` |
| Tests | `pytest`, `pytest-asyncio`, `pytest-textual-snapshot` |
| Paths | `platformdirs` (DB in the user data dir, config in the user config dir) |
| Time zones | stdlib `zoneinfo` |
| Config | TOML via stdlib `tomllib` (read-only; optional file) |
| IDs | UUIDv7 (use the `uuid-utils` package, or stdlib `uuid.uuid7` on Python 3.14+) |
| Migrations | Hand-rolled, versioned via `PRAGMA user_version` |

SQLite setup on every connection: `PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`.

## 3. Core concepts

### 3.1 Logical day (the 5am rule)

- `logical_day(now_local, day_start_hour=5) = (now_local_wall_clock - timedelta(hours=day_start_hour)).date()`
- At 02:00 on Tuesday the logical day is Monday. At 05:00 Tuesday it becomes Tuesday.
- Logical days are stored as `YYYY-MM-DD` text, **computed once at write time** and never recomputed from timestamps, so DST changes and travel cannot rewrite history.
- `day_start_hour` defaults to 5, is stored in `settings`, and may be overridden in the TOML config.
- The clock is **injected** (a `Clock` protocol with `now() -> aware datetime`) into the service layer. Tests use a fake clock.
- The app only ever **writes** to the current logical day. Past days are read-only.

### 3.2 Done, cancel, and tombstones

- Marking done upserts `completions(habit_id, day)` with `state='done'`.
- Canceling sets `state='cleared'` (a tombstone). **Do not delete rows**: this keeps the schema sync-ready. Queries treat `cleared` as "not done".
- Every write sets `updated_at` (UTC ISO-8601) and `device_id`.

### 3.3 Habit lifetime

- A habit has `created_day` and optional `archived_day` (logical days, stored as text).
- A habit is **active on day D** if `created_day <= D` and (`archived_day IS NULL` or `archived_day > D`).
- Days before a habit existed are blank (n/a), never "missed".
- Archive instead of delete. History is never lost.

## 4. Data model

```sql
-- PRAGMA user_version = 1

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);                               -- device_id (UUIDv7, generated on first run)

CREATE TABLE settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);                               -- day_start_hour = '5'

CREATE TABLE habit_groups (
  id          TEXT PRIMARY KEY,  -- UUIDv7
  name        TEXT NOT NULL,
  emoji       TEXT,
  sort_key    TEXT NOT NULL,     -- fractional/lexicographic key for cheap reordering
  created_day TEXT NOT NULL,
  archived_day TEXT,
  updated_at  TEXT NOT NULL
);

CREATE TABLE habits (
  id          TEXT PRIMARY KEY,  -- UUIDv7
  name        TEXT NOT NULL,
  sort_key    TEXT NOT NULL,
  group_id    TEXT REFERENCES habit_groups(id),  -- NULL for plain habits
  group_pos   INTEGER,                           -- 1..N inside a group, NULL otherwise
  created_day TEXT NOT NULL,
  archived_day TEXT,
  updated_at  TEXT NOT NULL,
  CHECK ((group_id IS NULL) = (group_pos IS NULL))
);

CREATE TABLE completions (
  habit_id   TEXT NOT NULL REFERENCES habits(id),
  day        TEXT NOT NULL,      -- logical day, YYYY-MM-DD
  state      TEXT NOT NULL CHECK (state IN ('done','cleared')),
  updated_at TEXT NOT NULL,      -- UTC
  device_id  TEXT NOT NULL,
  PRIMARY KEY (habit_id, day)
);

CREATE INDEX idx_completions_day ON completions(day);
CREATE INDEX idx_habits_group ON habits(group_id, group_pos);
```

Notes:
- A **group** is N ordinary `habits` rows sharing a `group_id`, with `group_pos` 1..N. Completions, history, and future sync therefore work unchanged. Groups only add a display and behavior layer.
- A group's own `sort_key` positions it in the list as a single row. Member habits do not appear individually.
- Plain habits and groups share one ordering: the Today list interleaves them by `sort_key`.
- `habit_groups.updated_at` and `archived_day` follow the same rules as habits.

## 5. Behavior

### 5.1 Plain habit (single row)

- **Toggle** (`space` or `enter`): done ↔ not done for today.
- Rendered as `[x] Read` / `[ ] Read`.
- After toggling, the cursor auto-advances to the next row. Exception: do not advance when the user un-toggles.

### 5.2 Habit group (multi-count row)

- Created with `Name x8` in the add prompt: creates the group and 8 member habits (`group_pos` 1..8). Accept an optional leading emoji (`💧 Water x8`). Valid count: 2 to 50. Anything else is treated as a plain habit name.
- Rendered as one row: `💧 Water ▪▪▪□□□□□ 3/8`.
- **Tick** (`space` or `enter`): marks done the lowest-`group_pos` active member that is not done today. If all are done, do nothing (no wrap, no error).
- **Clear last** (`backspace`): marks cleared the highest-`group_pos` member that is done today.
- The user never chooses which box. This keeps capture friction at zero.
- Auto-advance only when the group becomes fully done.
- **Resize** (`+` / `-` on the group row):
  - `+` adds a member at `group_pos = N+1` with `created_day = today`.
  - `-` archives the highest-`group_pos` active member (`archived_day = today`).
  - Minimum size is 2. Maximum is 50.
  - Past days keep their history. Because activity is determined per day (section 3.3), earlier days show the old denominator.
- **Archive** archives the group and all its members as one unit. Restoring does the reverse.

### 5.3 Progress line

Default behavior (decided): **each tick counts.** The line shows total ticks over total active habits, where a group with N members contributes N. Example: Water 3/8 plus two plain habits with one done is `4 of 10 today`.
- Partial progress always moves the number up.
- Copy is always neutral or positive. At zero it reads something like `Fresh day, ready when you are`.
- Never render red, "failed", "missed", or a negative count anywhere.

### 5.4 Rollover at 5am

- While the app is open, schedule a timer for the next boundary (and also re-check periodically, e.g. every 30–60 s, to survive suspend/resume and clock changes).
- On boundary: reload the Today list for the new logical day and show a gentle notification (e.g. `New day, fresh start ☀️`). Preserve cursor position by row identity when possible.

### 5.5 Review screen

Read-only. Reached with `tab` (cycles Today ↔ Review). Contains:
1. **Yesterday**: list of habits and groups with their results (blank for not done, never red), plus a warm one-line summary such as `You did 6 of 9 yesterday`.
2. **This week**: per-day totals for the last 7 logical days.
3. **Heatmap**: GitHub-style grid of the last ~12 weeks drawn with block characters. Each cell's shade is `done_ticks / active_habits` for that day.
   - Partial days get a lighter shade (not "incomplete"). A day with 3/8 water is visibly something.
   - A day with zero active habits is blank/empty.
   - Palette is cool and warm greens or similar. Avoid red entirely.

Stats are **positive-only**: counts and "X of the last 14 days". No streaks, no resets, no "days missed".

## 6. Keybindings

Both vim keys and arrows work. No modes. A footer shows the relevant keys on every screen.

| Key | Action |
|---|---|
| `j` / `↓`, `k` / `↑` | Move cursor |
| `g` / `G` | First / last row |
| `space`, `enter` | Toggle habit, or tick next box on a group |
| `backspace` | Clear last ticked box on a group |
| `a` | Add habit or group (one-line prompt; `Name x8` makes a group) |
| `e` | Rename |
| `d` | Archive (no confirm dialog) |
| `u` | Undo last archive (session-level restore) |
| `+` / `-` | Grow / shrink group |
| `J` / `K` (shift) | Move row down / up (reorder) |
| `tab` | Switch Today ↔ Review |
| `?` | Help (basic keybinding list; richer overlay in ROADMAP) |
| `q` | Quit |

Principle: **undoable instead of confirmable.** No "are you sure?" dialogs.

## 7. Project layout

```
habits/
  pyproject.toml
  README.md
  PLAN.md
  ROADMAP.md
  src/habits/
    __init__.py
    __main__.py          # entry point: `habits`
    core/                # pure Python, NO imports of textual or sqlite3
      clock.py           # Clock protocol, SystemClock, logical_day()
      models.py          # dataclasses: Habit, HabitGroup, Completion, TodayRow, GroupProgress
      service.py         # use-cases: toggle, tick_group, clear_last, add, rename, archive, restore, resize, reorder, today_view, review_view
      stats.py           # positive-only stats, heatmap intensity
      parsing.py         # parse "Name x8" / emoji prefix
    db/
      connection.py      # open DB, pragmas, platformdirs path
      repo.py            # SQL only; returns models
      migrations/
        0001_init.sql
    ui/
      app.py             # Textual App, screen switching, rollover timer
      screens/
        today.py
        review.py
        help.py
      widgets/
        habit_row.py
        group_row.py
        heatmap.py
        add_prompt.py
      styles.tcss
    messages.py          # all user-facing copy in one place (easy to tweak)
  tests/
    core/
    db/
    ui/
```

Dependency rules: `ui → core ← db`. The UI never touches SQL. Core never imports Textual or `sqlite3`. The service depends on a repository interface (a `Protocol`) so it can be tested with an in-memory SQLite or a fake.

## 8. Engineering practices

- **Testing**
  - Table-driven tests for `logical_day` (04:59 vs 05:00, midnight, DST spring-forward and fall-back, month and year boundaries).
  - Service tests against in-memory SQLite (`:memory:`) with a fake clock.
  - Group behavior tests: tick order, clear-last, resize, archive/restore, past-day denominators.
  - Textual Pilot tests for key flows (add, toggle, group tick, tab, archive + undo).
  - A few snapshot tests (Today and Review screens).
- **Quality gates**: `ruff check`, `ruff format --check`, `pytest` must pass before each milestone is considered done. Add type hints throughout; run `mypy` or `pyright` if convenient.
- **Migrations**: forward-only, numbered SQL files, applied in a transaction, `user_version` bumped. Refuse to open a DB with a newer `user_version` than the app knows.
- **Performance**: cold start should feel instant. Avoid heavy imports at startup and load only today's data on launch.
- **Data safety**: WAL mode; all multi-row operations (creating a group, archiving a group) run in a single transaction.
- **Config**: optional `config.toml` (`day_start_hour`, `timezone` override). Defaults need no file.
- **Commits**: small, one logical change each, conventional commit messages.

## 9. Milestones

Each milestone ends with passing lint and tests and a short manual check. Build in order.

### M1. Foundation
- Project scaffold (`uv`, `ruff`, `pytest`, entry point).
- `core/clock.py` with `logical_day()` and an injectable `Clock`, plus thorough tests.
- Schema (including groups), migration runner, `0001_init.sql`, `device_id` generation.
- `db/repo.py` with CRUD for habits, groups, completions.
- Core models and the service skeleton.

**Done when:** logical-day tests pass; a fresh DB is created with the full schema; repo round-trips work against in-memory SQLite.

### M2. Today view
- Textual app shell with the Today screen and footer key hints.
- Navigate the list (`j`/`k`/arrows, `g`/`G`).
- Toggle a plain habit done or not done (`space`/`enter`), with auto-advance.
- Progress line (each tick counts).
- Grouped rows: `space` ticks the next box, `backspace` clears the last ticked box. Render `💧 Water ▪▪▪□□□□□ 3/8`.
- Empty state with a friendly prompt to press `a`.

**Done when:** with seeded data, you can navigate, toggle plain habits, and tick and clear group boxes; state persists across restarts; Pilot tests cover these flows.

### M3. Managing habits and groups
- **Habits (single):**
  - Add by name (`a`).
  - Rename (`e`).
  - Archive (`d`), with undo to restore (`u`).
  - Reorder (`J`/`K`).
- **Groups (multi-count):**
  - Add with `Name x8` syntax, creating the group and its 8 members in one transaction.
  - Rename the group.
  - Archive the group as one unit, archiving and restoring all members together.
  - Reorder the group as a single row.
  - Adjust size with `+` and `-` (add a member / archive the highest-position member), within 2 to 50.

**Done when:** all of the above work from the keyboard with no confirm dialogs, and service tests cover every group operation including past-day denominators.

### M4. Review and rollover
- Review screen (`tab`): yesterday, this week, and the heatmap with partial shading.
- Positive-only summary lines in `messages.py`.
- 5am rollover refresh with a gentle notification, tested using a fake clock.

**Done when:** the heatmap renders correctly for partial group days and pre-creation days, and the rollover test proves the Today list swaps to the new logical day without a restart.

### M5. Release
- Packaging via `uv` (`uv tool install .` gives a working `habits` command).
- `README.md` (what it is, install, keybindings, data location, config).
- CI (GitHub Actions): ruff, tests, build.
- Version `0.1.0`.

**Done when:** a clean machine can install and run the app from the README alone, and CI is green.

## 10. Decisions already made

| Question | Decision |
|---|---|
| Language | Python + Textual |
| Habit types | Daily yes/no only; multi-count via groups |
| Backfill | None. Past days are read-only after the 5am rollover. |
| Streaks | None |
| Sync | Not now; schema kept sync-ready |
| Multi-count display | One grouped row per group |
| Progress line | Each tick counts toward the total (default; easy to change in `core/stats.py` if you prefer one-row-per-group) |
| Categories, encouragement polish, help overlay, export | Deferred to ROADMAP.md |
