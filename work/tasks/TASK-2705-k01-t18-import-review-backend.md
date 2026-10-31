---
id: TASK-2705
title: K-01-T18 Import review backend and migration methodology_imports
spec: SPEC-000  # K-01-T18 row, K-01 §3.6 and docs/contracts/methodology-programs.md
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: K-01
plan_key: K-01-T18
branch: s22-k01-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-10-31
updated: 2026-10-31
---

## Objective
- **[AC-1]** "The seeded EBP v3 import diffs against v2 as 4 added, 9 changed, 1 removed and 54
  unchanged on every run, and approve returns 409 while a flag is open."

## Scope
**In**: migration 0580 (four tables, event kinds, the frozen trigger's review opening); models,
registry; `imports.py` (create, upload, start, cancel, download, diff, standards mapping, flag
resolution, activity); `diff.py`; `import_routes.py`; approve's `flags_open` / `unverified_sources`;
seed v3 rewording; error catalogue, audit registries, contract, generated client; tests.
**Out**: the importer workflow, page extraction and quote verification (K-01-T20, T21); the
viewer's page endpoint (T20); KNW-02 UI (T19); independent ADR-078 suite (T24).

## Plan (amber)
1. Migration 0580 revises 0524 (re-chain at merge); expand-only; insert-only grants; the trigger
   replacement restores 0224's body on downgrade.
2. Registry and error catalogue edits; `methodology.import_review` gates the routes.
3. Tests first: unit lineage diff golden (4/9/1/54, determinism, similarity pass); integration
   (diff golden over HTTP, flags_open then confirm then approve, unverified_sources, idempotent
   imports, files_missing, file_exists, flag off 404, standards_set_invalid).
4. Rollback: downgrade 0580; revert the PR.

## Progress log
- `2026-10-31` — built; ruff, pyright clean on the touched files; `make generate` run. Tests run at the S22 end review (with the migration applied).

- `2026-10-31` — S22 end review: lint-imports and BOUND-002 refused methodology → evidence (moved
  to a platform file-store slot); the integration suite found 0580's trigger failing every
  `programs` write (field resolution in one IF) and an idempotent replay with no audit event; the
  security review found the download header unsafe for quotes and non-Latin-1 names, and no role
  check on uploads. All fixed (DEC-1759); generated security tests regenerated; `test_app_gates`
  lists the import routes. **Made twice:** a PL/pgSQL trigger shared by several tables reading a
  column only one has; candidate lint: a `TG_TABLE_NAME` test must guard field reads in its own IF.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1759 | end-review fixes: storage slot, trigger, replay, header, roles | No |
| DEC-1755 | storage through evidence, trigger opening for flags in review, seed rewording | No |
