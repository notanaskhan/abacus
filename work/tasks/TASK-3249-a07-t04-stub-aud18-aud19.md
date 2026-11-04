---
id: TASK-3249
title: A-07-T04 contract stub part 1 (AUD-18 EQR; AUD-19 completion, subsequent events, legal letters, going concern)
spec: SPEC-644
acceptance_criteria: [AC-4]
risk_zone: red
status: in-review
epic: A-07
plan_key: A-07-T04
branch: s27-a07-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"The generated client exposes every AUD-18 and AUD-19 operation returning 501, each route
declares one matrix action, and the I-AGENT-NEVER generated test covers eqr.concur."

## Plan (red)
- `assurance/completion_contract.py`: classified models (`EqrReviewOut`, checklist, digest
  cards, notes, concurrence; `AuditCompletionOut` and items; subsequent events and procedures
  with the bring-down; legal letters; going concern) and 18 routes under
  `/v1/audits/{work_item_id}`. Gate: client 404, work item 404, `authorise` with the work item
  in the resource (so `function_in` can bind), then 501. No flag until A-07-T33 (P-10 R2
  precedent, A-07 §0).
- Matrix (`assurance.yaml`): 11 new actions; `completion.read` and `eqr.concur` widened
  (DEC-2261). Every write denies agent, system and client principals.
- Contract doc sections; `make regenerate` (matrix, generated security suites, OpenAPI, client).
  Schema set diffed: 26 added, none removed or renamed.
- Tests: `tests/unit/assurance/test_a07t04_stub.py`.
- Rollback: revert and regenerate.

## Progress log
- 2026-11-04: built; duplicate operation id `going_concern` (A-06's SPEC-314 route) fixed by
  naming the route `audit_going_concern_route`. Tests at the S27 end review.

## Decisions made during this task
DEC-2230.
