---
id: TASK-396
title: SHL-01 toolbar data, routing and hotkeys from nav.ts (P-01-T02)
spec: docs/screens/SHL-01.md
acceptance_criteria: [AC 1.1.1, AC 1.1.2, AC 1.1.3, AC 1.1.4, AC 1.1.5, AC 1.1.6, AC 1.1.7, AC 1.1.8]
risk_zone: green
status: done
epic: P-01
plan_key: P-01-T02
branch: p01-t02-shl01-toolbar
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"The 13 SHL-01a strips pass Tier A and the toolbar's Tier D styles hold." The firm toolbar renders
the 13 items of `nav.ts`, lights the item from the manifest's `navArea` (b, g) or none in settings
(f), applies DF-39's overflow order (e), shows the bell dot from `unread_count` polled every 60 s
and on focus (a, d), opens interim Go… and Support frames, binds ⌘K and the G-chords, and gives
every planned area a flag-off landing instead of a 404. Scenarios a–g, each with a test.

## What changed
- **Toolbar data** `apps/web/src/shell/firm/ToolbarData.tsx` (`useFirmToolbar`), mounted by
  `legacy/Layout.tsx` in place of its three-item nav, `areaOf` and the SPEC-302 palette.
- **Area registry** `apps/web/src/app-core/nav-areas.ts`: per nav label, landing screen, path,
  `routed`, G-chord; `activeArea()`. It sits in app-core because the shell, the routes and the
  screen all need it, and app-core is the one root they may all import. It does not import the
  manifest: the manifest's handoff names ("Brightwater Hale") would then ship in `dist/`, which
  `gallery/dist.test.ts` forbids. SHL-01.test.tsx holds the table and the manifest in step.
- **Manifest** `navArea` field (types.ts) on the 13 landings, ENG-02, CLI-02 and the 8 R2 screens;
  ENG-01 routed at `/engagements` (legacy Engagements index); SHL-01 `fixture`.
- **Routes** `routes/firm/areas.tsx`: `/engagements`, and F-05-T19's `FlagOffState` at the path of
  each area whose landing is unrouted (Tax Returns, Files, Workbench, Inbox, Binders, Notices,
  Audits, Closes, Signatures).
- **Hotkeys** `shell/firm/hotkeys.ts`: G H/T/A/C/W and `?`, never from an input, textarea, select
  or contenteditable, never with a modifier. ⌘K stays AppShell's.
- **Interim frames** `shell/firm/InterimGo.tsx` (O5 `CommandPalette` over the 13 areas and the
  SHL-03 shortcut list, filtered in the browser, no request) and `InterimSupport.tsx` (O2 `Drawer`,
  "Accrued Support" and "System status"; addresses from `VITE_SUPPORT_EMAIL` and
  `VITE_STATUS_PAGE_URL`, never constants). Copy in `shell/firm/copy.ts`.
- **Bell** `useUnreadCount` now refetches on every window focus (`"always"`) besides the 60 s poll;
  it reads the v1 `GET /v1/notifications` `unread_count` (the v2 envelope is P-01-T01). The
  toolbar does not touch notification kinds (P-01-T03's `client_uploaded`, `mention`,
  `review_assigned` are the drawer's).
- **nav.ts** imports `nav` by name from scope-guards, so the banned-term table stays out of `dist/`.
- **packages/ui Toolbar**: `moreFirst`, `holdLabelWidth` and `goDetail` options, defaults unchanged
  (kit tests and specimens untouched); `fitToolbar({ moreFirst })` with tests. Rows in
  `packages/ui/src/tokens/DECISIONS.md`.
- **Screen** `apps/web/src/screens/SHL-01/` (index, scenarios a–g, copy, 22 tests) registered for
  `/components/screens/SHL-01?st=` by `src/screens/gallery.tsx`.
- **ESLint** (plan 04 §1.7): `src/screens/**` may also import `domain/<x>`, `routes/to|manifest`,
  `shell/firm/*` and `fixtures/scenario`; tests may import across feature roots. The rule had
  allowed only app-core, which left a screen no way to reach its builders or harness.
- **Parity** `docs/design/parity-manifest.json` `shl-01a.toolbar` (Tier A; harness learns `page` for
  gallery screen pages); Tier D block "SHL-01 toolbar" in `e2e/visual/tier-d.spec.ts`.
- **Docs** `docs/screens/SHL-01.md` (contract, deviations); DEC row in `docs/product/decision-log.md`.

## What the strips cover
- SHL-01a.png carries one toolbar (frame a, Home lit, 1400). `shl-01a.toolbar` Tier A: **0.11 %**
  (limit 0.5), blocking. The other 12 strips of frame b have no PNG; Tier D checks all 13 at 1400
  (width, step `signatures`, full firm name) and the state test checks the lit item of each.
- Tier D frame a: toolbar 46, lit and idle items 32 at Geist 13.5 (500/400), Go/firm/Support 30,
  bell 30 × 30, dot 6 × 6. Both Tier D tests and the Tier A test passed locally.

## Stubbed or interim
- Interim Go… replaces the SPEC-302 search palette in the toolbar until P-02 (AC 1.1.8);
  `shell/Palette.tsx` and its test stay. `?` opens interim Go… until SHL-03's dialog (P-01-T08).
- `firmTitle` is `firm_name` until `/v1/me` v2 gives the legal name (P-01-T04).
- Notification rows in scenarios are empty; only `unread_count` is set (rows: P-01-T07).

## Progress log
- 2026-10-22: built. Checks run: `tsc --noEmit` (only the pre-existing exactOptionalPropertyTypes
  errors inside generated `packages/api-client/src/client/*`), eslint and prettier on changed
  files, vitest on SHL-01, Layout, link-contract, gallery (dist included), shell, router, app-core
  and lint (360 passed), packages/ui layout in jsdom (96 passed), Playwright visual `parity` and
  `tier-d` (29 passed, other parity entries skipped for missing local baselines).
- 2026-10-22: found two things on the way. (1) `crop_handoff` rejects the current HANDOFF_VERSION
  ("2026-10-21 sha256:…"; it wants one token); the baseline was cut with a one-token version file.
  (2) The first toolbar import of the manifest and of scope-guards put handoff names in `dist/`;
  the dist test caught it.
