---
id: TASK-8852
title: "K-03-T08: Templates v2 contract stub (TV-1)"
spec: SPEC-720
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-k03t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: K-03-T08
---

## Objective
Every TV-1 route answers 501 under its one matrix action behind templates_v2.enabled, the api-client regenerates, and fixture mode serves every KNW-06, KNW-07, SHL-22 and SHT-03 artboard.

## Done
- methodology/templates_v2_contract.py
- engagements/templates_v2_contract.py
- routers registered
- make generate
- fixtures/seed/templates-v2.ts + foot test
- scenarios KNW-06, KNW-07, SHL-22, SHT-03
- docs/contracts/templates-v2.md
- DEC-5849

## Progress log
- `2026-11-20` — Plan (amber): contract-first stub; rollback = revert. Consumer tests are K-03-T10.
