---
id: TASK-8747
title: "F-08-T08: SheetLayout T18 (full and cockpit), sheet toolbar, row drawer O2 480, P/R column with C-25 slots, presence slots; states T18a-T18i"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s51-f08t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: F-08-T08
---

## Objective
T18a to T18i render from typed view models, a P or R slot click calls onOpenSignOff and never signs, and T18b scrolls with select and Key frozen.

## Plan (green)
1. `packages/ui/src/templates/sheet-layout.tsx`: the 44 px toolbar (view picker, saved views, + View, Filter · n amber with Clear, Columns, SearchField 200; Sign-offs, Agents, Comments), presence slot, the 64 px P · R column (C-25 chips or open P/R slots calling onOpenSignOff), the O2 480 drawer with the six tabs hosting slots, cockpit 696 px canvas beside the dock, and the empty (T18h copy, Add row) and loading (real header, 8 skeleton rows) views.
2. SheetGrid: a `trailing` column slot and `status.agentSummary`.
3. Tests: `sheet-layout.test.tsx`, one per state a-i plus the sign-off slot rules.
4. Rollback: revert the PR; no backend.

## Progress log
- `2026-11-19` — Built, stacked on #2385; sheet and template tests pass (templates 353), tsc and eslint clean. The handoff folder isn't on this machine: copy is from F-08 §3 A4 and docs/screens/T18.md, so screenshot parity and axe are still to do. Gates and tests run once at the S51 end pass (build first, test last).
