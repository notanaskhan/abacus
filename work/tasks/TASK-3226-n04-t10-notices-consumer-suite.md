---
id: TASK-3226
title: N-04-T10 Notices v1 consumer contract suite
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: N-04
plan_key: N-04-T10
branch: s26-n04-t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3226 · N-04-T10 · Notices v1 consumer contract suite

**Epic:** N-04 · **Sprint:** S26 · **Type:** TEST · **Zone:** green · **Depends on:** N-04-T02 · **Status:** in-review

## Built
`backend/tests/contracts/notices/test_n04t10_consumer.py`: status words against `status-vocabulary.yaml` (`notice`, `notice_intake`); intake and core refusal codes raised by the services (`low_confidence_unconfirmed`, `duplicate_unresolved`, `no_notice_engagement`, `not_ready`, `illegal_transition`); the contract document names `decision_pending`, `position_mismatch`, `not_ready`, `low_confidence_unconfirmed`; `position_mismatch` on the response view; amounts are tax return information; the human-only writes deny agent, system and client principals; NOT-01/NOT-02 field keys.

## Partial
- The TypeScript fixture assertions and the Whitley seed figures are not written yet (the screens' fixture rows, N-04-T09 onward).
- `decision_pending` and `position_mismatch` are asserted in the contract document only: the sign-off refusal lands with N-04-T12/T16.

## Progress log
- 2026-11-03: written; ruff and pyright clean; not run (end pass).
