---
id: TASK-8839
title: "T-08-T18: Filing-deadline readers in signatures and organisations"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-t08t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-08-T18
---

## Objective
Granite Peak's letter (Sep 16), the Ferris consents (Sep 23) and the Pryor 8879-F (Sep 28) arrive as deadline facts with owners and no document content.

## Done
- signatures/deadline_sources.py (envelope kind)
- organisations/deadline_sources.py (consent kind, renewals)
- registered at each api import
- tests/unit/signatures/test_t08t18_deadline_sources.py
- DEC-5841

## Progress log
- `2026-11-20` — Plan (red): two read-only providers; no migration; rollback = revert. Tests at the end pass.
