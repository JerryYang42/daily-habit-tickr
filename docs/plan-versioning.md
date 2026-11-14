# Release Versioning Plan

## Goal

Require each pull request to communicate its intended release impact before it
can merge, using a commit message that the release workflow can interpret.

## Current behavior

`.github/workflows/tag.yml` examines commits since the most recent version tag
and applies the highest matching bump:

| Commit signal | Version bump |
|---|---|
| Subject starts with `feat:` or `feat(scope):` | Minor |
| Subject uses `type!:` or `type(scope)!:`, or body contains a line starting with `BREAKING CHANGE:` or `BREAKING-CHANGE:` | Major |
| Anything else | Patch |

## Proposed merge rule

1. Require every pull request title to use the format
   `type(scope): description`, where the scope is optional and `type` is a
   lowercase word. For example: `feat: add habit export` or
   `fix(today): handle day rollover`.
2. Use `!` before the colon for any breaking change, for example
   `feat!: change the configuration format` or
   `fix(storage)!: rename the database columns`.
3. Use `feat` for a backward-compatible feature. Use another type, such as
   `fix`, `docs`, `test`, or `chore`, for work that should produce a patch
   release. Under the current release workflow, all non-`feat` and
   non-breaking changes produce a patch bump.
4. Require squash merges and use the pull request title as the squash commit
   subject. This makes the merged commit subject visible to the existing
   version computation. For breaking changes, put `!` in the title; do not
   rely only on a body footer.
5. Add a pull-request CI check that rejects titles outside the required format,
   then make that check required in the repository's branch protection rules.

## Implementation steps

1. Add a CI workflow check triggered by `pull_request` that validates the PR
   title against the accepted format. Keep the accepted syntax aligned with the
   subject patterns in `.github/workflows/tag.yml`.
2. Configure repository merge settings to allow squash merging and document
   that the PR title is the squash commit subject.
3. Mark the title-validation check as required for merging into `main`.
4. Verify the rule with representative titles:
   - `feat: add habit export` passes and results in a minor bump.
   - `fix(today): handle day rollover` passes and results in a patch bump.
   - `feat!: change the configuration format` passes and results in a major
     bump.
   - `Add habit export` fails validation and cannot merge.

## Acceptance criteria

- A pull request with an invalid title cannot merge into `main`.
- A squash merge preserves the validated PR title as the commit subject.
- Valid feature, ordinary change, and breaking-change titles map to minor,
  patch, and major bumps respectively.
- The release workflow continues to skip a commit already tagged at `HEAD`.