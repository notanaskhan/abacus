---
id: TASK-8317
title: "A-09-T20: Eliminations service on C8"
spec: SPEC-658
acceptance_criteria: [AC-4]
risk_zone: red
status: in-review
branch: a09-t20-eliminations
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-09-T20
---

## Objective
Spec section: docs/specs/SPEC-658 F4.
Eliminations service on C8.

## Plan (red)
1. `adjustments/eliminations.py` (exported as `adjustments.api.eliminations`): propose (a person; kind `elimination`, the consolidation, posting target `consolidation_layer`, display code `E<n>`, lines by caption with entity and level; the server's off-by), approve one or a batch (Manager or EP, a live person; 409 `unbalanced_entry`), post (approved to posted on the consolidation layer only: no posting batch, no snapshot), the lock refusal through `ledger.api.consolidation_facts`.
2. Audit kinds reviewed. Tests: `tests/unit/adjustments/test_a09t20_eliminations.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5313). Lint, pyright and the import contracts clean; the unit file ran green (3 tests). Partial: the AUD-33 routes in `assurance/group_contract.py` (list, create, edit, approve, reject) still answer 501; reject-with-reason reuses `adjustments.reject` once wired; consolidation-level AJE and RJE through A-06's propose path and the outbox events are not added. Gates and
  tests run once at the S47 end pass (build first, test last).
