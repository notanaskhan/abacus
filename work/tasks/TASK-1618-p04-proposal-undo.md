---
id: TASK-1618
title: Proposal Undo and effect hold (P-04-T29)
spec: SPEC-360
acceptance_criteria: [AC-4]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T29
branch: s13-p04-t29
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Undo a proposal decision inside 10 seconds by its decider, voiding held effects and putting back what it wrote; refuse once an effect has started.

## Plan
- `agents/proposal_undo.py` (`undo_proposal`, `undo_typed`); the undo route in `agents/contract.py`; `undo_until` in the decision view.
- Migration 0273 (down 0272): `proposals_state_guard()` accepts decided → pending with the undo.
- `review.api.previous_value`; `evidence.api.review_decision_engagement`.
- Test `tests/integration/backfill/test_p04t29_proposal_undo.py`. DEC-713 (the Temporal effect hold deferred: no Temporal-hosted proposal effect exists).
- Rollback: downgrade 0273; revert.

## Progress log
- 2026-10-28: built; tests in the batch pass.
