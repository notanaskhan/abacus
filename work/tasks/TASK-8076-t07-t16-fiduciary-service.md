---
id: TASK-8076
title: "T-07-T16: Fiduciary computation service"
spec: SPEC-656
acceptance_criteria: [AC-6, AC-7, AC-8, AC-9]
risk_zone: amber
status: in-review
branch: t07-t16-fiduciary-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T16
---

## Objective
TXT-02's workpaper over the fiduciary engine: insert-only FAI lines, expenses and distributions
edited by a person with citations and reasons, synchronous recompute into insert-only computation
versions (idempotent by inputs hash), refusal before an approved interpretation, the L2 reviewable
with Changed rows and struck priors, K-1 box provenance and the deterministic export.

## Plan (amber: written before the build)
1. `tax/fiduciary_service.py`: reads, adds and edits (versions with `set_by` and sealed reasons),
   `recompute_in` / `recompute` / `recompute_after_approval`, `computation` (tree with struck
   priors from the stale L2's signed version, by character, tallies, banner), `export_xlsx`
   (`workbook_of`, pure), the `fiduciary_computation` reviewable (L2).
2. `fiduciary_contract.py`: the T-07-T05 stubs served; `tax/api.py` registers the reviewable and
   recomputes when the instrument's L3 lock approves the interpretation.
3. Tests: `tests/unit/tax/test_t07t16_fiduciary_service.py` (3 pass locally); the version rows and
   the stale L2 sign-off land in the T-07-T20 AC suite (end pass).
Rollback: revert; behind `tax.fiduciary_workpapers` (default off).

## Progress log
- `2026-11-15` — Planned at the S46 kickoff (#2053); built (DEC-5061). Import check clean.
- **Partial within the row:** "Import from statement" refuses with 409 `statement_tables_missing`
  until the custodial-statement layout map exists (T-07 cut 4: manual entry with citations); the
  1041 "Type of entity" field link rides with T-07-T19's CCH map.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5061 | Reviewable keyed by the return; struck priors from the stale L2's signed hash; boxes as formula values | no |
