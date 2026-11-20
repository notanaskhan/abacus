---
id: TASK-8858
title: "Q-04-T230: Deadline week Oct 16-20 watch, window close, Oct 24 flips"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-q04t230
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-04-T230
---

## Objective
Show no release ran Oct 16-20, close autumn-2028 in windows.yaml, give the Oct 24 A-08 flips rollback refs.

## Done
- windows.yaml: autumn-2028 closed 2028-10-20; release_windows parses and checks 'closed' (on or after the last day), calendar prints it
- Watch doc with the P-29 gate over eleven instants (PF-X1, synthetic)
- Five A-08 flips on Oct 24 each with a rollback command and its off state
- Test test_q04t230_window_closed.py

## Progress log
- `2026-11-20` — 2026-11-20: done on PF-X1 (synthetic). Live canary, SES, second approver need a real firm. DEC-5855.
