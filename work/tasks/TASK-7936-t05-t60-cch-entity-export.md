---
id: TASK-7936
title: "T-05-T60: CCH file-bridge export section for entity returns (TTB by CCH line code, partner allocations by Schedule K line)"
plan_key: T-05-T60
spec: SPEC-651 (T-05 F11)
acceptance_criteria: [AC-F11]  # export before final approval refused; only a person marks the entity return transmitted
risk_zone: red
status: in-review
branch: t05-t60-cch-export
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
The entity return's export to CCH Axcess carries the TTB by CCH line code and the partner
allocations by Schedule K line from the approved checkpoint only; blocked while Unmapped > 0;
human-only after final approval; never transmit.

## Plan (red)
- Files: `tax/export_entity.py` (new: sheets from `values_as_of` at the checkpoint, Unmapped
  gate), `tax/export.py` (entity forms: gate before the grant; `workbook(..., entity=)` adds
  `TTB` and `Allocations`). No migration, no route, no matrix change (the export route and
  `tax_return.export` stand).
- Docs: `docs/contracts/tax-engine-bridge.md` §6 row.
- Tests: `backend/tests/unit/tax/test_t05t60_entity_export.py` (sheets, byte stability, gate,
  never-transmit extended to the entity path).
- Rollback: revert the PR; individual returns are unchanged.

## Partial
- The CCH Axcess entity layout is unvalidated (T-05 OQ-1, R-05): the CCH line code is the 1065
  form-line key until the pilot firm's own Axcess validates it in shadow.

## Progress log
- 2026-11-14: built; tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4931 | entity section on T-01's W2 path from the checkpoint's workbook; gate before grant | no |
