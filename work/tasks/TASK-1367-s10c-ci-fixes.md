---
id: TASK-1367
title: S10 wave C CI fixes on main ee7bdf04 (unit contract tests, matrix read classification, fixture journeys)
spec: SPEC-000  # no SPEC: a CI fix across SPEC-012, R-01 and G-01 (DEC-462, DEC-463)
acceptance_criteria: [AC-1]  # run 40417471929's unit, fixture-journey and ledger-schema failures pass
risk_zone: amber
status: in-review
epic: Q-03
plan_key: none
branch: s10c-ci-fixes
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Main went red after the S10 wave C batch (`ee7bdf04`, run 40417471929). Fix each cause without
weakening a test. Decisions DEC-462, DEC-463; defects ED-129, ED-130.

## Plan (amber)
- Unit: the exact-set contract tests that earlier `[skip ci]` merges left stale (the screening
  subscriptions, the worker's publisher routes, the module pre-registration, the stored firm
  settings) follow the decided additions; `audit_event.read_firm_level` becomes a read verb
  (DEC-462). `tests/unit/engagements/test_transitions.py` (`legacy_g2`) is left to PR #471.
- Journeys: the firm menu's Firm settings opens `/settings/general` behind `firm_settings.v2`;
  `RequestMobile` shows the other-parties note and opens a row; three spec locators corrected
  (DEC-463).
- No migration, no generated-file change, no new dependency. Rollback: revert the commit.

## Progress log
- 2026-10-27: built and verified. Integration shard 4/5 of the run also failed on
  `test_ledger_schema.py` (migration 0195's new connection columns and provider key grammar,
  #436 merged `[skip ci]`); its expectations follow DEC-439. Targeted pass: 8 unit files
  (10,477 passed, `-n 2`), 2 integration files (168 passed), J03/J12/J16 fixture journeys
  (14 passed, 1 fixme as before), POR-03, SHL-03, SHL-01 and the request kit in vitest. Gates:
  ruff, pyright, lint-imports, the six quality modules, tsc, eslint, prettier; `make regenerate`
  produced no change. Playwright ran on the cached chromium-1243 (no local config needed).
  Not mine: `test_transitions.py` (`legacy_g2`, PR #471) and `src/status/status.test.ts`.
