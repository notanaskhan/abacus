---
id: TASK-1126
title: ENG-01 Engagements index on T1 — segments, seven tiles that filter and foot, chips, search, G3 banner b, advisory c, empty d, loading e (P-07-T27)
spec: SPEC-321
acceptance_criteria: [AC-16, AC-23]
risk_zone: green
status: done
epic: P-07
plan_key: P-07-T27
branch: s7-p07-tests-fe
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Scenarios a to e pass with axe and the tiles sum to the header in every scenario." Contract:
`docs/screens/ENG-01.md`; handoff `ENG-01 Engagements index/` (README, spec.md; no revision).

## Plan
- `packages/ui`: T1 `IndexList` gains `segments` (before the chips), `IndexChip.align: "end"` (Period at
  the right end), `banner` (b's G3 banner above the table) and pending tile counts while loading (e);
  `StatusTile` gains `muted` and `soon` (with the lock) so the registry's engagement colours are tiles.
- `domain/engagements/list.ts`: filters and `useEngagementIndex` over the generated client.
- Fixtures: `seed/engagement-index.ts` (17 named rows + counted remainder, DEC-271),
  `handlers/engagements.ts` (the read model over the slice), `scenarios/ENG-01.ts` (a–e).
- Screen: `screens/ENG-01/{index.tsx,copy.ts,scenarios.ts,ENG-01.test.tsx}`; gallery entry; route
  `/engagements` behind `engagements.v2` (legacy while off); `e2e/screens/ENG-01.spec.ts` (axe).

## Progress log
- 2026-10-24: built; 21 ENG-01 tests, 5 footing tests; whole `apps/web` Vitest 138 files green,
  `packages/ui` 46 files green. Manifest stays `planned` (link-contract rule 1 needs `to.<ID>()`
  wiring otherwise, DEC-195). The e2e axe spec needs the Playwright run (`ABACUS_VISUAL=1`); not run
  here. Live E0 figures wait for the backend load to carry ENG-01's engagements (F-04-T31).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-271 | ENG-01's unnamed engagements, Type cell, sub-lines and Period │ Current on fixtures | No |
