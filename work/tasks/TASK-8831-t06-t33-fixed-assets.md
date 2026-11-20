---
id: TASK-8831
title: "T-06-T33: Fixed-assets service and routes"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-t06t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-06-T33
---

## Objective
An edit by Olivia Brandt changes nothing until a reviewer approves the proposal, and approval writes a checkpoint and re-ties 733,500.

## Done
- tax/fixed_assets_service.py (E3 reads, create, ghost change requests, reviewer decision, checkpoint, 02 projection)
- migration 0999 + registry
- matrix fixed_asset.approve_change + codegen
- TXP-03 routes live + approve/reject routes
- entity_sections open-flags slot (409 open_flags_note_required)
- activity_reviewed
- tests/unit/tax/test_t06t33_fixed_assets_service.py
- DEC-5833

## Progress log
- `2026-11-20` — Plan (amber): service, migration, matrix, routes, tests; rollback = downgrade 0999 and revert. make generate at the end pass (new routes). Tests at the end pass.
