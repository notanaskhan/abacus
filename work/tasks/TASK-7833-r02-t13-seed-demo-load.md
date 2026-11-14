---
id: TASK-7833
title: "R-02-T13: the seed-demo load read against the figures book"
spec: SPEC-000  # code partial (S0-S38 inventory, bucket C)
acceptance_criteria: [AC-1]  # the row's acceptance
risk_zone: green
status: done
branch: r02-t13-seed-demo-load
worktree: /Users/ayushkbhatia/Accrued/abacus-lo39-rec
created: 2026-11-14
updated: 2026-11-14
plan_key: R-02-T13
---

## Objective
"make seed-demo and fixture mode show identical data": TASK-7809 tied the seed code and the portal
fixture to one figures book statically; no load had been shown.

## Delivered (#1945)
- `tests/integration/test_r02t13_seed_demo_equivalence.py`: loads the `completion` and
  `governance_room` slices through the loader into their own database and reads back the four
  attest entries, AJE-1's lines and receivable total, PAJE-2's title and accrued lines, and the
  Benefits Committee's members and chair against `portal_figures.json`.
- Fixture-only by design: Copperleaf's posted entries and Meera's K-1.

## Progress log
- 2026-11-14: written; ruff and pyright clean. Not run locally (the test lock was held, then Docker
  stopped); it runs in the batch merge's CI.
- 2026-11-14: merged; passed in main CI 43522183908 (0152ac5d6). Row done.
