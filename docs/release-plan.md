# Release automation plan

Goal: replace "tag on every merge" with a **release PR** flow, so `pyproject.toml`, `uv.lock`, the git tag and the changelog always agree.

## Decisions

| Topic | Decision |
|---|---|
| Tool | [release-please](https://github.com/googleapis/release-please-action) with `release-type: python` |
| Versioning | Conventional Commits: `feat` is minor, `fix` and others are patch, `!` or `BREAKING CHANGE` is major |
| Release trigger | Merging the bot's release PR (not every merge to `main`) |
| Outputs | `vX.Y.Z` tag, GitHub Release with notes, `CHANGELOG.md`; no PyPI |
| Existing `tag.yml` | Removed (superseded) |

## How it works

1. Feature and fix PRs merge to `main` as today.
2. On every push to `main`, release-please opens or updates one PR titled `chore(main): release X.Y.Z`.
   - Bumps `version` in `pyproject.toml`.
   - Bumps the `habits` entry in `uv.lock`.
   - Prepends the new section to `CHANGELOG.md`.
3. When we want to release, merge that PR. release-please then creates the tag and the GitHub Release.

## Changes

1. **`.github/workflows/release-please.yml`**: trigger on push to `main`, with permissions `contents: write` and `pull-requests: write`. Use `googleapis/release-please-action@v4` with the config files below and a token (see Risks).
2. **`release-please-config.json`**:
   - `release-type: python`
   - `include-component-in-tag: false` so tags are `v0.2.0`, not `habits-v0.2.0`
   - `extra-files` entry for `uv.lock` using a TOML jsonpath `$.package[?(@.name=='habits')].version`
3. **`.release-please-manifest.json`**: `{ ".": "0.1.0" }` to match the existing `v0.1.0` tag.
4. **Delete `.github/workflows/tag.yml`**.
5. **`README.md`**: short "Releasing" note: use Conventional Commit titles; merge the release PR to ship.

## Risks and open points

- **CI does not run on bot PRs.** PRs opened with the default `GITHUB_TOKEN` do not trigger workflows, so required checks would never report on the release PR. Fix: give the action a fine-grained PAT or a GitHub App token (`contents` + `pull requests` write) stored as a repo secret. Needs a decision and a one-time setup.
- **`uv.lock` must stay in sync.** CI runs `uv sync --locked`, which fails if the lock's `habits` version differs from `pyproject.toml`. Verify the jsonpath edit works on the first release PR. Fallback: a small job that runs `uv lock` on the release PR branch and pushes the result.
- **PR titles matter.** We merge with merge commits, and release-please reads every commit in the PR, so each commit message needs a conventional prefix. If we move to squash merges, the PR title becomes the only thing that counts.
- **Pre-1.0 behaviour.** By default a breaking change bumps to 1.0.0. To stay on 0.x, set `bump-minor-pre-major: true` (breaking becomes minor) and `bump-patch-for-minor-pre-major: true` (feat becomes patch).
- **`habits --version`**: check where it reads the version from. If it uses package metadata, nothing else is needed.
- **Repo settings**: Actions must be allowed to create PRs (Settings, Actions, General, "Allow GitHub Actions to create and approve pull requests") unless a PAT or App token is used.

## Verification

1. Merge this change to `main`. release-please should open a release PR proposing the next version based on commits since `v0.1.0`.
2. Check the PR diff: `pyproject.toml`, `uv.lock` and `CHANGELOG.md` only, and CI is green.
3. Merge it. Confirm the tag, the GitHub Release, and that `main` still passes `uv sync --locked`.
4. Run `uv build` and confirm the wheel version matches the tag.

## Rollback

Revert the workflow and config files. Tags and releases already created are unaffected; delete them manually if needed.
