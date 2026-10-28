---
id: TASK-1620
title: Audit-trail metric reads for pilot metrics (Q-04-T006)
spec: SPEC-349
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: Q-04
plan_key: Q-04-T006
branch: s13-q04-t006
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Counts and first-to-last durations of allowlisted audit actions for one firm, identifiers only.

## Plan
- `audit_trail/metrics.py`, exported by `audit_trail.api`; migration 0275 (down 0274) adds the action-time index.
- Test `tests/integration/test_q04t006_audit_metrics.py`. DEC-715.
- Rollback: downgrade 0275; revert.

## Progress log
- 2026-10-28: built; tests in the batch pass.
