---
id: TASK-1508
title: I-01-T10 GET /v1/home live in practice
spec: SPEC-308
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: I-01
branch: s12b-i01t10
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Home's tiles, your-work band, deadlines and running count, role-shaped and office-filtered (DEC-648).

## Plan (amber)
- `practice/home.py` (service), `practice/home_contract.py` (route live), `engagements/home_work.py` (`assigned_work`).
- Tests: `tests/unit/practice/test_i01t10_home_rules.py`, `tests/integration/backfill/test_i01t10_home_live.py`; the stub contract test moved to live.
- Rollback: revert; the route answers 501 again.

## Progress log
- 2026-10-27: built; lint and pyright clean; app imports. Tests run in the S12 batch pass.
