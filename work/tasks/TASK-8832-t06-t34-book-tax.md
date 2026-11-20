---
id: TASK-8832
title: "T-06-T34: Book-tax service and routes"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-t06t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-06-T34
---

## Objective
The With proposed fix view previews 6,200 / 7,466,200 / 6,866,200 without writing, and a stale seen_version answers 409 proposal_changed.

## Done
- tax/book_tax_service.py (M-3 and M-1 from E4)
- TXP-04 m3/m1 routes live
- M-2 variants and C3 seen_version reused
- tests/unit/tax/test_t06t34_book_tax_service.py
- DEC-5834

## Progress log
- `2026-11-20` — Plan (amber): service + routes + tests; no migration; rollback = revert. Tests at the end pass.
