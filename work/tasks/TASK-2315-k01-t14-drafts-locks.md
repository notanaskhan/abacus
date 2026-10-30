---
id: TASK-2315
title: K-01-T14 methodology drafts and mandatory locks
spec: SPEC-008
acceptance_criteria: [K-01 AC5.1, AC5.2, AC5.3, AC5.4, AC5.7]
risk_zone: amber
status: in-review
epic: K-01
plan_key: K-01-T14
branch: s18-k01-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Draft vN+1 from a published version with step_key lineage; edit, add and remove non-mandatory
steps with If-Match; edits keep their source; QM-only mandatory route with fresh MFA; discard;
code-computed change list against drafted_from; audit events. (Submit is K-01-T06's, live.)

## Plan
- `methodology/drafts.py` (service); `lifecycle.record_refusal`, `lifecycle.view_in` exposed.
- `methodology/contract.py`: six routes live; `_stub` removed (no stub left).
- Migration 0464: UPDATE (mandatory, lock_note) for the app, person-only trigger, step event kinds.
- Error catalogue, generated client, contract doc error list, DEC-1361.
- Tests: `tests/unit/methodology/test_k01t14_drafts.py`, `tests/integration/backfill/
  test_k01t14_methodology_drafts.py`; the K-01 stub contract test now asserts the routes live.
- Rollback: revert; 0464 downgrade drops the trigger and grant (fails if step events exist).

## Progress log
- `2026-10-30` — built (DEC-1361). Unit (7) and contract (48) tests run once; the integration
  test waits for the S18 end review. `[skip ci]`. 0464 revises 0430: re-chain onto 0463.

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** T-01-T22; K-01-T15 (frontend) and K-01-T16 (independent tests) consume this.
