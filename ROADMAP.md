# Roadmap

Where `habits` is headed after v0.1.0. For how it works today, see [docs/design.md](docs/design.md); for what has shipped, see [CHANGELOG.md](CHANGELOG.md).

**Don't build anything here until someone explicitly asks for it.** When an item is picked up, open a GitHub issue for it, link the issue here, and keep the details in the issue. When it ships, remove it from this file and add it to the changelog.

## Now

Nothing in progress.

## Next

- [ ] **Separate modes for ticking and managing.** Today every key works at all times, so a stray `d` or `e` while you're quickly ticking things off can archive or rename a habit. Split the Today screen's keys into two modes:
  - **Tick mode** (the default, for daily use): move (`j`/`k`, arrows, `g`/`G`), tick (`space`/`enter`), clear (`backspace`), switch to Review (`tab`), help (`?`), quit (`q`).
  - **Manage mode** (for changing the list itself): add (`a`), rename (`e`), archive (`d`), undo (`u`), resize groups (`+`/`-`) and reorder (`J`/`K`). Moving the cursor works the same as in Tick mode.
  - `m` switches to Manage mode, and `esc` (or `m` again) goes back to Tick mode. The app always starts in Tick mode, and it returns to Tick mode after switching to Review and back.
  - Make the current mode obvious: a label in the header (for example, `Managing`), a different cursor color, and a footer that shows only that mode's keys.
  - Manage mode stays on until you leave it. It doesn't switch back after an action, so you can add or rearrange several habits in one go.
  - Each mode has only its own keys. `space`, `enter` and `backspace` do nothing in Manage mode, and `u` does nothing in Tick mode. To undo an archive, switch back to Manage mode first.
  - Still no confirmation dialogs. Archiving stays undoable.
  - This reverses the "no modes" rule in [docs/design.md](docs/design.md) section 5.7. When it's built, update that section, the decisions table, the README key table and `messages.HELP_ROWS` (the `?` screen), and split each of them by mode.
  - Implementation hint: add a `mode` attribute to `TodayScreen` and check it in the existing `check_action`, which already hides keys by row type and refreshes the footer.
- [ ] **Categories** (for example, Health, Work, Home)
  - An optional `categories` table and a nullable `category_id` on habits and groups (needs migration `0002`)
  - Today view grouped under collapsible category headers
  - Filter by category, and per-category stats on the Review screen
  - A key to cycle or filter categories, and a way to set the category from the add/edit prompt
  - Open question: a group must belong to one category as a unit (its members inherit it)
- [ ] **Filter the Today list.** Add views for **All**, **To do** (not done yet) and **Done**. In All, show unfinished rows first and done rows after them, with each part keeping your manual order. A group counts as done only when every box is ticked.
  - Choose a key: `tab` already switches to Review. Options include `f` to cycle the views, or `1`/`2`/`3`.
  - Decide how `J`/`K` reorder works while the list is filtered or sorted, and how the cursor behaves when a row you just ticked moves to the Done part.
- [ ] **Align row names.** Plain habit names and group names should start in the same column. Today `[ ] Read` starts its name after the checkbox, but `💧 Water ▪▪▪□□□□□ 3/8` starts at the left edge, so the two kinds of row look out of line. Give group rows a leading column the same width as `[ ]`, and check that emoji of different widths still line up.

## Later

- [ ] **Sync across devices.** The schema is already ready for it (UUIDv7 IDs, `cleared` tombstones, `updated_at`, `device_id`). The likely rule is last-write-wins per `(habit_id, day)`. Reordering already writes one row at a time.
- [ ] **A small non-interactive CLI** on the same core (for example, `habits done water` or `habits list`) for scripts and quick capture
- [ ] **A forgiving, positive-only alternative to streaks**, such as "active days this week" (only if streaks are ever wanted)
- [ ] **Backfill of the previous day**, with a gentle "forgot to tick it" flow. Out of scope by design for now: past days are read-only, and undo is limited to the same day.
- [ ] **Encouragement copy**
  - Rotating warm messages when a habit is checked off
  - A "welcome back" tone after a gap in use (never "you missed N days")
  - A small celebration on a perfect day
  - A setting to turn messages down or off
  - All copy stays in `messages.py`, so it's easy to tweak
- [ ] **Help overlay** (`?`): a full, searchable list of keys. v0.1.0 has only a basic list.
- [ ] **Export** to JSON and CSV, so data is never locked in
  - Include habits, groups and completions (tombstones optional)
  - Consider a matching import
