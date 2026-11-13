---
id: TASK-7909
title: W-02-T14 WB-01 list pane and header
plan_key: W-02-T14
spec: SPEC-653
acceptance_criteria: [AC-L1, AC-L2, AC-L3, AC-L4, AC-L5]  # WB-01c and f; Running 3 → Running 4
risk_zone: green
status: in-review
branch: w02-t14-wb01-list
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
SessionList bound to the list query and realtime, the filter menu with counts, search and its f
state, row markers, via-Agent meta, inline rename, the delete dialog, and the header (Bug to WB-09,
planned Create Agent…).

## Plan
- Kit: `packages/ui/src/agent/chat/session-list.tsx` (additive props).
- Screen: `apps/web/src/screens/WB-01/{index.tsx,copy.ts,WB01.test.tsx}`; route
  `routes/firm/workbench.tsx` writes `?filter=`.

## Partial
- The Paperclip chip's count needs a read of the session's attached context (no read route; the
  attach and remove routes answer it); the chip draws without a count until W-02-T16/T17.
- axe runs with the end-pass vitest (the gallery's axe harness); not run here.

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4912 | server counts only; additive kit props; owner-only manage | no |
