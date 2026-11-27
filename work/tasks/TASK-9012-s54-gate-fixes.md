---
id: TASK-9012
title: "S54-GATES: Banned-patterns fixes across the S54 stack"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s54-gate-fixes
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: S54-GATES
---

## Objective
The banned-patterns gate (make check-fast) passes over the whole S54 stack, with every finding fixed at its cause.

## Done
- kernel.vendor_pages slot (BOUND-002)
- tax reads through owner APIs (OWN-001)
- typed K-1 flow slot (CAST-001)
- agents api import (BOUND-001)
- Seeder for owner fixtures (DB-001)
- typing reasons (ANY-001, TYPE-001)

## Progress log
- `2026-11-26` — Gate exit 0; 60 tests of the touched rows pass (C-02-T45/T46, T-06-T50/T51, T-08-T30/T33/T34, CV-2 CLI).
