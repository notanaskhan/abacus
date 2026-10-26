---
id: TASK-1306
title: Migration methodology_reown - methodology owns its tables and code; version lifecycle (K-01-T02)
spec: SPEC-008
acceptance_criteria: [AC-3]
risk_zone: amber
status: in-review
epic: K-01
plan_key: K-01-T02
branch: s10-k01-knowledge
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Move SPEC-008's methodology tables and code from `engagements` to `methodology`, add the version
lifecycle and events and the global `standards_sets`, and backfill every legacy version as
published (`legacy_import`).

## Plan
- Files: `methodology/{models,workbook (moved),repository,service,routes,registry,api}.py`;
  `engagements/{models,repository,service,routes,api,registry,onboarding,roll_forward}.py` lose
  the methodology code; `engagements.api` re-exports what other modules already import.
- Migration `0180_methodology_reown` (first in this block; `down_revision = "0172"`): template
  `family`; version `label`, `drafted_from_version_id`, `origin`; `methodology_version_states`
  (mutable, column grants), `methodology_version_events` (insert-only, trigger),
  `standards_sets` (global), `engagements.standards_set_id` FK; backfill.
- Registry: methodology owns the seven tenant tables and `standards_sets`; `schema_check`
  `GLOBAL_TABLES` gains `standards_sets`; LIST_EXEMPT paths follow the moved functions.
- Acceptance: `tests/integration/test_k01t02_methodology_migration.py` (legacy rows read
  published with `legacy_import`; up/down/up; schema check) and
  `tests/integration/backfill/test_k01t02_methodology_reown.py` (an import publishes and moves the
  default; the five tables and the events stay insert-only); import-linter keeps methodology on
  identity and platform.
- Rollback: downgrade 0180 (drops the new tables and columns; the five tables are untouched) and
  revert the code move.

## Progress log
- 2026-10-26: built; import-linter and banned patterns clean; tests in the end-of-batch pass.
- 2026-10-26: targeted pass green (contracts, backfill, migration up/down/up with the schema check, unit, security); gates clean. The schema check needed the five tables' insert columns in the methodology registry (moved from engagements, plus 0180's new ones).
