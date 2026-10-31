---
id: TASK-2424
title: K-02-T18 Brightwater Hale firm standards through the import endpoints
spec: SPEC-000  # the backlog row; K-02 §3 F5, US-3.5, US-5.1
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: K-02
plan_key: K-02-T18
branch: s19-k02-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Brightwater Hale content through the import endpoints in `scenarios/brightwater_hale`: AJE
thresholds v1 and v2, six TY2025 checklists plus the 1040 v7 draft, review levels, BH-TAX-02,
variance v3, materiality v2, document confidence v1, SSARS off, owners, demo-clock examples;
`make fixtures` export; staging reference sets loaded with the CLI.

Acceptance: "make seed-demo and fixture mode show identical KNW-04 data and the 20,020 and
224-return footings hold as seed tests."

## Plan
- Slice `standards.py` (events), loader handlers, `SLICE_NEEDS`.
- `methodology.api` loading calls (`standards_loading.py`) over the route's own functions.
- `fixture_export`: the `standards` slice, flag and read.
- Seed tests: `tests/unit/synthetic/test_k02t18_standards_slice.py`.

## Progress log
- `2026-10-31` — Built on `s19-k02-t18` off main 7d4def8e5. DEC-1472. To do at the end review:
  run `make fixtures` to commit `e0.standards.json` and pin any date gaps in `exported.test.ts`.
  Human: `make refdata-publish` on staging for the platform reference sets.
