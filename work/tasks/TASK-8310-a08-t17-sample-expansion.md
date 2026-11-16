---
id: TASK-8310
title: "A-08-T17: Sample expansion (AUD-12 R2)"
spec: SPEC-657
acceptance_criteria: [AC-3]
risk_zone: amber
status: in-review
branch: a08-t17-sample-expansion
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-08-T17
---

## Objective
Spec section: docs/specs/SPEC-657-a08-audit-fieldwork-depth.md F3.
Sample expansion (AUD-12 R2).

## Plan (amber)
1. Migration `0931_sample_expansions.py` on 0930: required rationale, a named approver who is not the requester, human-only decision by that approver (CHECKs), the resulting version on approval, one open expansion per sample set; column grants.
2. `sampling/expansions.py`: `expand` (prefix kept, next by score, seeded unpredictable), request (422 `expansion_rationale_required` / `approver_required`), decide (named approver only; `seen_hash` 409 `content_changed`; approval appends a version and dispatches the draw), withdraw; domain events; the `sample_expansion_approval` HOME-02 gate (`assigned_only`).
3. `sampling/je_draw.py` (red path, the sampler's draw): a version naming an `expansion` is drawn by `expand` from the base version's items, refusing any drift; `je_tests.dispatch_draw` factored out.
4. `review/gates.py` (protected): C13 subscribes to `sample_expansion.requested/decided`.
5. Routes in `sampling/fieldwork_contract.py`; registry; audit kinds reviewed.
6. Tests: `tests/unit/sampling/test_a08t17_expansion.py`. Rollback: `alembic downgrade 0930`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5307). The app imports (the gate source registered after its events were added to C13); the unit file ran green (3 tests). Partial: Northwind's "Add participants" by named key (AC-3.4) is refused on a JE sample (`sample_items.selection_reason` has no named reason); the approver's notification kind is not added. Gates and
  tests run once at the S47 end pass (build first, test last).
