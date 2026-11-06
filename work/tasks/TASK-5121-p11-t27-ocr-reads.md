---
id: TASK-5121
title: P-11-T27 fields, tables and regions live; a person's text retry
spec: SPEC-000  # row (P-11-T27)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T27
branch: s29-p11-t27
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
C4 v1.1's three 501 routes live, and field matches lighting their boxes in SHL-08.

## Plan
evidence/ocr_reads.py; ocr_contract.py live; viewer.viewer_regions adds field matches; ocr_step exposes gate_facts, REFUSAL_WORDS, API. Rollback: revert; routes stay behind their flags.

## Progress log
- 2026-11-06: built. `backend/tests/unit/evidence/test_p11t27_ocr_reads.py` written, not run (end pass). Pyright, ruff, banned patterns clean.

## Decisions made during this task
DEC-2417
