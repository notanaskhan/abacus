---
id: TASK-2904
title: A-04-T16 independent acceptance tests for A-04-T03, T04, T06, T13 (ADR-078)
spec: SPEC-620
acceptance_criteria: [AC-15, AC-16, AC-19]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T16
branch: s24-a04-t16 (stacked on s24-a04-t13)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

Independent tests, written from the plan and the AUD-08 handoff rather than the builders' tests, for the workpaper core, the planning migration and the risk register.

## Acceptance (backlog)

Every AC in sections 3.1 and 3.4 that your tasks implement has a test written that passes on main without edits to your tests.

## Plan

- `tests/unit/assurance/test_a04t16_register_independent.py`: RMM golden over all twelve IR×CR pairs of BH matrix v1, a missing pair never guessed, tally against the handoff grid (10 / 2 (+1) / 2 / 3 / 1, Pending), approval states, register hash, area keys.
- `tests/integration/backfill/test_a04t16_planning_independent.py`: INV-4 client 404 on the planning and workpaper reads, INV-3 another firm 404, independence 403, INV-5 attribution of `risk.created` and every field through the history, management override Mandatory and never rebuttable, a stale edit writes nothing, linking twice 409 and unlinking keeps the row.
- Already covered on main and not duplicated: 0613's guards (T06's migration suite), the workpaper core's staleness, override reason and byte-identical export (T04's suite).

## Progress log

- 2026-11-01: written in abacus-s24, stacked on A-04-T13. Not run (build first, test last).
