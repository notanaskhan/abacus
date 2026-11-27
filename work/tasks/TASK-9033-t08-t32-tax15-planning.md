---
id: TASK-9033
title: "T-08-T32: TAX-15 planning opportunities a-f on T9"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s54-t08-t32-tax15
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-08-T32
---

## Objective
TAX-15 a-f on T9 close-review with the portfolio strip: banded queue with rings, detail with Why This Was Surfaced, evidence pane, raise sheet (O3 until INB-04), create-project prefill to ENG-03, dismiss reasons and Show dismissed, consent-blocked banner to SIG-02, per-return client chip.

## Done
- TAX-15 a-f render from data
- A raise sends only on Daniel Reyes's click
- The Ferris row offers Open consent envelope and no outreach
- Opportunity read gains consent basis, owner and tax year (Postgres test)
- Fixture from the Python scenario

## Progress log
- `2026-11-27` — 2026-11-27: built per DEC-6038. 8 TAX-15 tests and the route and link suites green. Links wired: TAX-15 to TXP-01 and CLI-05, TXP-01 to TAX-15. Mistake: overwrote a tracked planning_slice.py with Write and restored it from git. Lesson: check the path exists before writing a new file.
