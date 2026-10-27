---
id: TASK-1511
title: K-01-T06 methodology lifecycle service (submit, approve, supersede)
spec: SPEC-008
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: K-01
branch: s12b-k01t06
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Submit, a code-computed checklist, human-only approve with an effective date that supersedes the prior version, refusals audited, pin by acceptance date, the review notification (DEC-651).

## Plan (amber)
- No migration (0180 and 0224 hold the states, events and freeze). `methodology/lifecycle.py`, `methodology/events.py`, live routes and a state read in `methodology/contract.py`; `engagements.api.pin_methodology_on`; notification kind `methodology_review_requested`.
- Tests: `tests/integration/backfill/test_k01t06_methodology_lifecycle.py`; K-01 stub tests moved to live.
- Rollback: revert; the routes answer 501 again.

## Open
- The C13 gate kind waits for firm-level gates in the projection (DEC-651).

## Progress log
- 2026-10-28: built; lint and pyright clean; app and worker import. Tests run in the S12 batch pass.
