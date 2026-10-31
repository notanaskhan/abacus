---
id: TASK-2425
title: T-01-T33 Live swaps (code half): TAX-09 export checkpoint and sync facts
spec: SPEC-000  # the backlog row; T-01 §3.9, TAX-09, CLI-05
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: T-01
plan_key: T-01-T33
branch: s19-t01-t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-31
updated: 2026-10-31
---

## Objective
Live swaps: TAX-09 popover and import sheet onto the bridge routes, CLI-05 consents onto C19, the
sync chip on TAX-01 and TAX-02 rows, the agents-off DF-04 state on T-01 surfaces; support for
P-04's SHL-16 import variant.

Acceptance (staging half is a human step): "TAX-09 and CLI-05 consents run live on staging with
the flags on for synthetic firms, and no fixture handler is reachable in the staging build."

## Progress log
- `2026-10-31` — Code half on `s19-t01-t33` off main 7d4def8e5: `EngineSyncOut.checkpoint_id`,
  live blockers and approver; TAX-09 posts the live checkpoint. The rest was already live
  (DEC-1473). Staging flip and the fixture-handler check are human to-dos.
