---
id: TASK-2813
title: A-05-T07 Northwind EBP scenario slice 1
spec: SPEC-640
acceptance_criteria: [AC-5]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T07
branch: s23-a05-t07
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "make seed-demo loads the slice, fixture mode shows identical figures, and every
  figure-book total foots in the seed tests."

## Plan (amber)
- `brightwater_hale/ebp.py`: figure book (census, payrolls, W-3, providers, plan facts), eight
  synthetic documents, the `ebp` slice; loader handler through `evidence.api`; golden YAML.
- Tests: `tests/unit/synthetic/test_a05t07_ebp_slice.py` (every total foots; documents
  deterministic). To run at the end review: the loader's slice integration (`--slice ebp`).
- Plan facts and providers load with A-05-T08's service. Rollback: revert.

## Progress log
- `2026-11-01` — built; ruff and pyright clean; figure book smoke-footed (301 / 14,560,000 /
  746,600; 26 payrolls; late deposit 9 business and 10 calendar days). Tests at the end review.

## Decisions made during this task
DEC-1862.
