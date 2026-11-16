---
id: TASK-8079
title: "T-07-T22: Estate workpapers backend (migration 0892, estate engine, routes)"
spec: SPEC-656
acceptance_criteria: [AC-12, AC-13, AC-14]
risk_zone: amber
status: in-review
branch: t07-t22-estate-workpapers
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T22
---

## Objective
The Form 706 workpaper behind TXT-04: inventory, deductions, computation, gifts and derivations
over a pure estate engine, insert-only inputs set by a person, the due chip, and Approve values
at L4.

## Plan (amber: written before the build)
1. Migration **0892** `estate_workpapers` (expand-only): profiles, inventory items, deductions
   and gift history (per client entity) with insert-only versions, insert-only computations.
2. `tax/compute/estate.py` + protected `parameters/estate/ty2026.yaml` (BEA 15,000,000; §2001(c)
   schedule; annual exclusions; IL exclusion 4,000,000).
3. `tax/estate_service.py`: reads (recomputing into a new version when inputs moved), edits
   (versions with sealed reasons; `valued` needs a citation), derivation tiles, due chip from
   `practice.api.due_dates_for` (statutory fallback), the `estate_values` L4 reviewable.
4. `estate_contract.py` routes served; `tax/api.py` registers the reviewable.
5. Tests: `test_t07t22_estate_engine.py` (5), `test_t07t22_estate_due.py` (1), pass locally.
Rollback: revert; downgrade drops the eight tables; behind `tax.estate_workpapers`.

## Progress log
- `2026-11-15` — Built (DEC-5063). Also fixed T-07-T16's inserts naming `id` (not app-insertable:
  `RETURNING id`). Engine figures reproduce the row's acceptance exactly.
- **Partial within the row:** Request appraisal… stores the C5 request item on the asset version
  (`request_item_id`); composing and sending it is SHL-14's (T-07-T26). The Illinois card has a
  status and no figure by design.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5063 | Gift history per client entity; computations recomputed on read when inputs move; statutory due fallback | no |
