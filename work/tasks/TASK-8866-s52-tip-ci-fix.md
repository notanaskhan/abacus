---
id: TASK-8866
title: "S52: S52 tip CI fixes"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-ci-fix
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: S52
---

## Objective
Fix what the S52 tip CI found.

## Done
- pyright: boto3 client var, WORKFLOWS WorkClass type
- status vocabulary: SheetVmOut.status and TaxDepthNexusOut.state are not statuses; agent run 'stopped' is the vocabulary's cancelled
- QBO port conformance and fixed lists (vendors, UPDATE columns, archived-write allowlist, examples slot, inspector stub)
- J02 7 asserts Publish v1 disabled (handoff); T4 context trigger and EliminationCard ARIA (axe)

## Progress log
- `2026-11-20` — 2026-11-21: fixed and checked locally. Pre-existing on main, not S52: J10 3, J16 8, J20 2/5/6/7/8 (fail on 282d7e367 too). DEC-5863.
