---
id: TASK-8830
title: "T-06-T39: Tax-side hand-off landing"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-t06t39
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-06-T39
---

## Objective
Replaying the event creates no second issue, the banner reads 'From FY2026 audit · Final TB · handed off Nov 9', and nothing is written to the audit engagement.

## Done
- migration 0998 tax_handoff_landings + tax registry
- tax/tb_handoff_landing.py subscriber (idempotent), issues as the person, draft mapping, landing read model
- ledger/tb_handoff.py reads
- C12 read routes and the return landing route live
- activity_reviewed tb_handoff.received
- tests/unit/tax/test_t06t39_tb_handoff_landing.py
- DEC-5832

## Progress log
- `2026-11-20` — Plan (amber): migration, subscriber, reads, routes, tests; rollback = downgrade 0998 and revert. Targets/preview/create assembly follows as the T-06-T20 rest PR. Tests at the end pass.
