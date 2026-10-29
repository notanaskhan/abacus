---
id: TASK-2108
title: T-01-T07 T-01 rows of the S16 protected bundle
spec: SPEC-501
acceptance_criteria: [AC-13, AC-14]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T07
branch: s16-t01-t07
created: 2026-10-29
updated: 2026-10-29
---

## Objective
T-01's protected rows: the W2 file-bridge entry, red-path notes, NEVER-ERO-001 and TAXAPPROVE-001,
and the egress assertion (T-01 §4.9). Matrix rows and flags landed with T-01-T01/T02.

## Plan (red)
- `write-capabilities.yaml` note on `tax_engine_file_bridge`; `protected-paths.md` tax red files.
- `banned_patterns.py`: two rules; `tests/unit/quality/test_banned_patterns_tax.py`.
- Rollback: revert.

## Progress log
- 2026-10-29: built (S16 block; tests run at the batch's end review). DEC-1158.
