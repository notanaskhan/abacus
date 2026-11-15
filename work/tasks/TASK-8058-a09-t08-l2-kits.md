---
id: TASK-8058
title: "A-09-T08: L2 kits — C-35 EntityTree, C-38 MilestoneTimeline, CoverageBar, with specimens"
spec: SPEC-658
acceptance_criteria: [AC-0]
risk_zone: green
status: in-review
branch: a09-t08-l2-kits
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-09-T08
---

## Objective
The three L2 kits the group screens mount, each with a gallery specimen, EntityTree reordering by
keyboard alone.

## Plan
1. `packages/ui/src/data/{EntityTree,MilestoneTimeline,CoverageBar}.tsx`; exports in `data/index.ts`.
2. `specimens/group-audit.tsx` registered in `specimens/index.ts`.
3. `data/group-kits.test.tsx`.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010).
- `2026-11-15` — Built (DEC-5043). tsc and eslint clean. Tests and the axe pass on the specimens
  run at the end pass.
