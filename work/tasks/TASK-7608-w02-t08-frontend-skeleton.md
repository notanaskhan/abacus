---
id: TASK-7608
title: "W-02-T08 frontend skeleton: routes, manifest, domain, screen contracts, palette command"
plan_key: W-02-T08
spec: SPEC-653
acceptance_criteria: [AC-L2, AC-L3, AC-V1, AC-C1, AC-C2, AC-D3]
risk_zone: green
status: in-review
branch: w02-t08-frontend-skeleton
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The Workbench subtree on fixtures: routes, manifest entries, the `domain/workbench` layer, screen
contracts WB-01 to WB-03, the SHL-02 "New session…" command, and fixture mode on the T02/T03 stubs.

## Plan
- `routes/firm/workbench.tsx` (new): `/workbench` (`filter`, `q`, `session`), `/workbench/sessions/new`,
  `/workbench/sessions/$sessionId`, all behind `workbench.enabled` (off: F-05 flag-off state);
  the `?ov=artifact:<id>` O4 overlay. Registered in `routes/firm/index.ts`; the Workbench nav area is
  routed (`app-core/nav-areas.ts`), so its planned landing retires.
- `routes/manifest/wb.ts`: WB-01, WB-02, WB-03 `fixture` with paths; WB-04, 06, 07, 10, 12 stay planned.
- `domain/workbench/` (new): `queries.ts`, `mutations.ts`, `realtime.ts` (`session:<id>`, `user:<id>`),
  `index.ts`. `app-core/realtime.ts`: several domains may register one topic kind (TAX-08 and W-02
  both read `session:<id>`); the keys compose.
- Screens (skeletons): `WB-01` (the list, filters, title search, "+" via `to.WB02()`, the locked
  row), `WB-02` (the blank session and the four suggested prompts, `copy.ts`), `WB-03` (the thread
  host, `to.WB01()`; `ArtifactPreview` O4 over the stored artifact).
- HOME-01's "3 running" pill links to `/workbench?filter=running` when `workbench.enabled` is on
  (`DashboardLayout.runningHref`); SHL-02's legacy palette gains "New session…" behind the flag.
- Fixtures: `fixtures/handlers/workbench.ts` mounted in the E0 scenario.
- Screen contracts `docs/screens/WB-01.md`, `WB-02.md`, `WB-03.md` with their parity tables.
- Test `apps/web/src/routes/w02-workbench-routes.test.ts`.
- Rollback: revert; the flag is off.

## Deviations (DEC-4607)
- The screens are skeletons: the thread states (T17), the picker and answer (T16) and the run arc
  (T21) are later rows; their fixture scenarios arrive with them (the screen-scenario registry is
  untouched here).
- The palette command goes into the current palette; P-02-T10's `CommandPaletteData` carries it over.

## Progress log
- `2026-11-12` — Skeleton built (DEC-4607). Tests run at the S40 end pass.
