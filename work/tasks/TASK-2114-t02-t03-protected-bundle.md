---
id: TASK-2114
title: T-02-T03 T-02 rows in the S16 protected bundle
spec: SPEC-502
acceptance_criteria: [AC-1, AC-2]
risk_zone: red
status: in-review
epic: T-02
plan_key: T-02-T03
branch: s16-t02-t03
created: 2026-10-29
updated: 2026-10-29
---

## Objective
T-02's matrix rows (tax, requests, evidence, portal), four flags, fresh-MFA rows, K1RELEASE-001 and
the I-AGENT-NEVER extension (T-02 §4.4, §4.9, §4.10).

## Plan (red)
- Matrix files, flag files, fresh-MFA register; `make regenerate`.
- `identity/authz/matrix.py` action pattern allows digits; `banned_patterns.py` K1RELEASE-001;
  `codegen/security_tests.py` resolution entities.
- Rollback: revert.

## Progress log
- 2026-10-29: built (S16 block; tests run at the batch's end review). DEC-1162, SPEC-502.
