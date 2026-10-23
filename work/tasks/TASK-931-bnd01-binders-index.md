---
id: TASK-931
title: BND-01 Binders index, states a, c, d, e in fixture mode on T1 (P-06-T09)
spec: SPEC-319
acceptance_criteria: [AC-7, AC-8, AC-10]
risk_zone: green
status: done
epic: P-06
plan_key: P-06-T09
branch: TASK-931-bnd01-binders-index
created: 2026-10-23
updated: 2026-10-23
---

## Objective
BND-01 at `/binders` (behind `binders.engine`) on T1: filter chips, status tiles that filter the
rows, ledger rows with progress, a row ··· menu (Publish, Unpublish…, Duplicate as pt n, Open in
Files) and the "New binder…" sheet, with a fixture scenario and a test for each of a, c, d and e.
Acceptance (P-06-T09): "Four scenarios pass their Vitest tests and axe, and the tiles filter the
rows and foot to 241."

## What changed
- **Screen** `apps/web/src/screens/BND-01/`: `index.tsx` (L4 over T1 `IndexList`; `BND01`
  controlled by filters, `BindersIndex` holding them), `copy.ts` (spec.md verbatim), `scenarios.ts`
  (a, c, d, e plus the search each opens on), `BND-01.test.tsx` (21 tests).
- **Domain** `apps/web/src/domain/requests/` (`binders.ts`, `index.ts`): `useBinders`,
  `useBinderActions` (publish with an Idempotency-Key and a 10-s Undo through
  `/publish/undo`, unpublish with a reason, duplicate), `useNewBinder`, `useStaffNames`, the
  filter model and `defaultBinderFilters(today)` (the season is the year before the business date).
  Generated client only.
- **Fixtures** `fixtures/seed/binders.ts` (the 15 spec rows, Osterberg for c, the §9.5 counts),
  `fixtures/scenarios/BND-01.ts` (`GET /v1/binders` in the `ListPage[BinderRowOut]` shape with
  every filter, counts over the filters minus the tile; publish, undo, unpublish, duplicate and
  create), `fixtures/binders.foot.test.ts`.
- **Route** `routes/firm/binders.tsx`: `/binders`, F-05's flag-off state while `binders.engine` is
  off. `nav-areas.ts` Binders `routed: true`; manifest BND-01 `fixture`, path `/binders`.
- **Gallery** `/components/screens/BND-01?st=a|c|d|e` in the shell frame.
- **E2E** `apps/web/e2e/screens/BND-01.spec.ts`: each artboard at 1440×900 DPR 2, axe 0 serious or
  critical (run locally: 4 passed).
- **Docs** `docs/screens/BND-01.md`: manifest status, DV-12 to DV-15, parity row, open gaps.

## Tests mapped to ACs
- AC-10 (tiles foot to 241) → `BND-01 acceptance: tiles foot to 241`, `binders.foot.test.ts`.
  The wall half of AC-10 is server-side (P-06-T11, T17).
- AC-7 (unpublish needs a reason) → `Unpublish… asks for a reason and sends it`.
- AC-8 (Duplicate as pt 2) → `the menu offers Duplicate as pt 2 …`.

## Progress log
- `2026-10-23 05:10` — Built on fixtures: `GET /v1/binders` is still the C5 stub (501) until
  P-06-T11. P-06-T08's Python slice (TASK-921) landed during the session; the TS rows agree with it
  (kind `organizer`, statuses, preparers, activity dates) except Osterberg's progress (gap below).
  apps/web typecheck (no new errors outside the known api-client set), lint, vitest
  (fixtures, screens, gallery, routes: all green), Playwright `e2e/screens/BND-01.spec.ts` 4/4.
  SHL-01's AC 1.1.5 list drops "Binders" because the area is routed now; its flag-off page is
  asserted in BND-01.test.tsx instead.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Openers end in "…": "New binder…", "Unpublish…" (DV-12) | Plan 04 rule 9, asserted in development | no |
| Tiles hidden while loading (DV-13) | A tile must never read 0 it does not have; skeleton tiles need a T1 change | no |
| The summary reads a `part` facet ("1", "2+") | Facets are open-keyed; T11 emits it without a contract change | no |
| Fixture gives Grace and Remy `binder.publish`/`binder.create` | The canvas has Grace publish and unpublish; firm setting `client_service_can_publish` assumed on | no |

## Gotchas and discoveries
- **Missing row facts (stopped, not invented):** `BinderRowOut` carries no marked-done person and
  date, closing reason, overdue count, internal-draft line or request window, and last client
  activity has no actor, summary or thread link. The status cell shows the pill (and the
  Unpublished line, whose facts exist); the activity cell shows the date. P-06-T11 owns these.
- No firm binder-template list in C5: the sheet offers Blank only.
- "Send reminders…" and b are P-06-T16's; T1 has no slot for a second header action.
- The Ferris consent tag is not drawn: tags are codes with no label registry yet.

## Handoff
- **Current state:** done, merged.
- **Exact next step:** P-06-T11 (read model incl. the row facts above and the `part` facet), then
  P-06-T16 (b, follow-up sheet, live swap, search params).
