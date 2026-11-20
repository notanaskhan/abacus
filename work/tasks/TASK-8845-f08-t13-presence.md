---
id: TASK-8845
title: "F-08-T13: Presence base endpoint and anchors"
spec: SPEC-660
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-f08t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: F-08-T13
---

## Objective
PUT /v1/presence accepts cell, section and card anchors only for registered kinds, heartbeats expire after 45 s, and nothing is audited or sent through the outbox.

## Done
- migration 1001 presence_heartbeats (UNLOGGED)
- kernel/ephemeral.py
- platform/presence.py + presence_routes.py
- realtime TOPIC_KINDS presence
- engagements registers work_item
- matrix presence.update/read + codegen
- docs/contracts/presence.md
- tests/unit/platform/test_f08t13_presence.py
- DEC-5844

## Progress log
- `2026-11-20` — Plan (amber): migration, kernel helper, service, routes, contract, tests; rollback = downgrade 1001 and revert. make generate at end pass.
