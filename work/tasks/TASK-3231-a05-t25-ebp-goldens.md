---
id: TASK-3231
title: A-05-T25 EBP goldens and engine properties
spec: SPEC-640
acceptance_criteria: [AC-8, AC-18, AC-21]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T25
branch: s26-a05-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3231 · A-05-T25 · Independent AC tests and goldens for the EBP services and engines

**Epic:** A-05 · **Sprint:** S26 · **Type:** TEST · **Zone:** amber · **Depends on:** A-05-T10, T16, T19, T20, T22 · **Status:** in-review

## Built
`backend/tests/golden/ebp/test_a05t25_ebp_goldens.py` (ADR-078): the Northwind figure book with exact Decimal equality (plan profile, census = W-3 = payroll 14,560,000.00 and deferrals 746,600.00, receivable 15,060.00 + 33,540.00 = 48,600.00); the late remittance is 9 business days (Jan 1 excluded); entry is the later of age 21 and three months; hypothesis properties (missed contributions idempotent and to the cent; matching hire dates need no review); an engine version bump changes every inputs hash.

## Partial
- EBP-03's per-participant figures (the 25 sampled, missed-deferral amounts) are not transcribed: the figure book has no per-participant rows. Import and provision-service goldens are not added.

## Progress log
- 2026-11-03: written; ruff and pyright clean; not run (end pass).
