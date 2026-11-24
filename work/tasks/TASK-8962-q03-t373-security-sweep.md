---
id: TASK-8962
title: "Q-03-T373: Security and reliability sweep 2028 Q4"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-quarterly-sweeps
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-24
updated: 2026-11-24
plan_key: Q-03-T373
---

## Objective
Every new table and condition kind has generated tests, no high DAST or GuardDuty finding open, every burn-rate alert followed up.

## Done
- generator_coverage: 0 gaps (tables, isolation, conditions, decisions; S53 tables 1010 to 1018)
- compliance invariant catalogue: the full suite on the batch tip
- end-pass security fixes listed (presence check, DEC-5941, two-year accept order)

## Progress log
- `2026-11-24` — 2026-11-24: partial: DAST, Inspector, GuardDuty and ADR-093 follow-ups need staging and AWS (DEC-1389).
