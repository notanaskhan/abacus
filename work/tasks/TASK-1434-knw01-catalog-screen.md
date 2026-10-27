---
id: TASK-1434
title: KNW-01 Knowledge library on the T5 CatalogLayout (K-01-T04)
spec: SPEC-008
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: K-01
plan_key: K-01-T04
branch: s11-home
created: 2026-10-27
updated: 2026-10-27
---

## Objective
KNW-01 a-f from fixtures with the 48-item footings; search marks never use the match purple; Ana
Cruz sees no + menu and no drafts. `/knowledge` replaces Knowledge.tsx (behind
`knowledge.catalog`).

## Plan
- Contract: `KnowledgeItemOut.usage_kind` (the words a usage count reads in); `make generate`.
- `packages/ui`: `CategoryList` count optional (no provider, no count); `CatalogLayout` `bare` and
  a tabsbar `label`.
- `domain/knowledge/{categories,queries,index}` (addendum §4 order, tones, usage words).
- `screens/KNW-01/{index,copy,scenarios,KNW-01.test}`; `fixtures/seed/knowledge.ts` (48 cards,
  2 queue rows, 4 change-log rows, verbatim), `fixtures/handlers/knowledge.ts`,
  `fixtures/scenarios/KNW-01.ts`, `fixtures/knowledge.foot.test.ts`; gallery artboard; route
  `/knowledge` behind `knowledge.catalog` (legacy otherwise), lazy; manifest `fixture`.
- Every target (KNW-02/03/04/05, WB-07, ENG-01, TAX-14) is planned: Open, Review and the + items
  are disabled with "Not built yet" in dev and fixture builds and absent in production.
- g and h (Oct 1 counts, engagement templates) need K-03's and later providers; not built here.
- Axe and Playwright not run in this lane.

## Progress log
- 2026-10-27: built.
