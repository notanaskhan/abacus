---
id: TASK-6530
title: "R-02-T17: POR-09 Deliverables frontend"
spec: SPEC-646
acceptance_criteria: [AC-1]  # the row's acceptance (Objective)
screens: [POR-09]
risk_zone: green
status: in-review
branch: s33-r02-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: R-02-T17
---

## Objective
POR-09 a, a2, b, c, d and f render from live data and e from fixtures, every figure comes from the
API, and the 390 layout keeps a sticky Approve.

## Build
- `apps/web/src/screens/POR-09/` (`index.tsx`, `copy.ts`, `scenarios.ts`, `POR-09.test.tsx`) on
  T7 split: rail (bands, Coming next, My K-1s, registry status words), viewer (pager and zoom over
  the server's page PNGs through the generated client, DRAFT watermark on drafts, AR-C 70 legend,
  comment column from `…/comments`), Download through `…/download`, Approve on the latest version
  only when it lists `approve` (confirm "Approve the 2025 financial statements (the latest
  draft)?", `seen_hash` and an Idempotency-Key; 409 shows "A newer draft is available"), d's K-1
  card is POR-13's `PackageCard` (T-02's routes and consent sheet, DV-09), f empty, flag-off,
  390 with the sticky Approve.
- Portal route `/deliverables[/$id][?section=k1s]` mounts the screen; Deliverables moves into
  production's nav map (`AREA_PATHS`); the shell-hooks test expectation follows.
- Fixtures: `seed/portal-r02.ts` (rail, versions, comments), `seed/portal-k1s.ts`
  (`meera_released`), `scenarios/POR-09.ts` (a-f and the flag-off state).

## Progress log
- `2026-11-09` — Built; tests written, not run (end pass). Partial: "live data" waits on R-02-T09's
  deliverables routes, which still answer 501 (list, detail, version, pages, download, approve,
  comments); the screen reads them through the generated client, so it goes live with them
  unchanged. The comment composer is drawn (the handoff's) but posting waits on R-02-T22's
  comments route; g-i stay deferred (DV-06).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3130 | POR-09's flag-off state is a 404 on the list read; the flag-off words follow EBP-08's | no |
