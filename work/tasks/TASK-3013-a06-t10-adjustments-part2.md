---
id: TASK-3013
title: A-06-T10 adjustments service part 2 — approve-and-send, Undo, batch, reject, record mode
spec: SPEC-642
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T10
branch: s25-a06-t10 (stacked on s25-a06-t09)
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-02
updated: 2026-11-02
---

## Objective
"A send writes one decision row and one batch at once, nothing reaches the client before the grant
is released, Undo inside 10 seconds voids it, and no route or adapter can post an entry."

## Plan (red)
- `adjustments/decisions.py`: send (grant-held event), undo_send, create_batch, reject,
  record_client_decision, slots `register_client_delivery`, `register_entry_decision_hook`.
- Routes served; new `POST /v1/approval-batches/{id}/undo`; `make generate`.
- `assurance/completion.on_entry_client_decision` registered as the hook.
- Rollback: revert.

## Acceptance
| Check | Test |
|---|---|
| 10-second window; digest binding; fail-closed delivery; person only; nothing posts | `tests/unit/adjustments/test_a06t10_decisions.py` |

## Progress log
- 2026-11-02: built; client regenerated. Integration suite and security review at the S25 end review.

## Decisions made during this task
DEC-2062.
