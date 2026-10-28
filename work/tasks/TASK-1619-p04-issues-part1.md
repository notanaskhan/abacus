---
id: TASK-1619
title: Issues service part 1 (P-04-T30)
spec: SPEC-360
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T30
branch: s13-p04-t30
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Create, update and assign, list and read issues on a reviewable; blocking issues feed the sign-off and final-approval checks; engine diagnostics dedupe on source_ref.

## Plan
- `review/issues.py`; routes in `review/contract.py`; the `open_issues` check in `review/sign_offs.py`.
- Migration 0274 (down 0273): `GRANT INSERT (id) ON issues`; registry.
- Tests `tests/integration/backfill/test_p04t30_issues.py`; `test_c3_stub3.py` leaves the four live routes out of its 501 check.
- DEC-714. Rollback: revert; downgrade 0274.

## Progress log
- 2026-10-28: built; tests in the batch pass.
