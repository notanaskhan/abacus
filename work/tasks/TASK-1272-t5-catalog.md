---
id: TASK-1272
title: T5 CatalogLayout with the C-11 AgentCard and IconTile and the C-14 ConnectionTile; T5a to T5f and TPL-05a to TPL-05e (F-05-T59)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T59
branch: s9b-kit-screens
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The library shows 28 agents (Audit 3/1/1) and Connect shows 9 of 53 (9+38+6) with monogram tiles
and no vendor logos or brand colours." (F-05 F4: TPL-05c's "payroll tax" yields the EmptyState
with Clear search.)

## Scope
**In**
- `packages/ui/src/catalog/catalog-kit.tsx`: the grammar both kits share. `CatalogBadge` (words
  from the `agent_template` and `integration` registry objects; installed and connected, which
  the registry gives as the olive check disc, draw as the kits' solid olive badge), `CatalogCard`
  (white, radius 12, e2, e3 on hover over 200ms, no lift for coming soon), `CatalogSkeletonCard`
  (tile and three bars), `CatalogGrid` (three columns, gap 12, a list) and `CategoryList` (34 band,
  33 or 46 rows with count pills, listbox with ↑ ↓ Home End).
- `packages/ui/src/agent/agent-card.tsx` (C-11): `AGENT_TONES`, `IconTile` (34, the seven tones
  as token fills with white Lucide glyphs), `AgentCard` (210; Details… or Notify me / Notifying
  you). Beside notanaskhan's `agent/blocks.tsx`, which renders agent text and is not reused here:
  nothing on a catalog card is agent output.
- `packages/ui/src/connect/connection-tile.tsx` (C-14): `ConnectionTile` (212; F-05-T13's
  `VendorTile` monogram on the first category's colour, tags joined by " · ", the scope line,
  Enable · Details… / Details… · Disconnect / Notify me; Connecting… disables Details…).
- `packages/ui/src/templates/catalog-layout.tsx`: `CatalogLayout` (tabsbar 50, the optional 44
  sub-row with a left-aligned small Segmented, the C-09 `library` preset: 358 side pane with the
  search row, AboutCard and CategoryList beside the grid pane with the status Picker, the centred
  title, the optional right search and the shell well, padded 10 14 14 or 14).
- `packages/ui/src/specimens/t5.tsx`, `t5-data.ts`: `t5-catalog` (T5a to T5f) and `tpl-05`
  (TPL-05a to TPL-05e), the 28 agents and 53 integrations of the canvases the boards mount.
- Registry, exports, parity (`docs/design/parity-manifest.json` Tier B entries with a deviation)
  and two Tier D checks in `apps/web/e2e/visual/tier-d.spec.ts`.

**Out**
- The Details panel (WB-05), the Edit Agent sheet behind + (WB-07), the Connect drawer behind
  Enable (WB-11), the Sessions tab (T4) and the 420ms skeleton on each filter change.

## Definition of done
- [x] 21 tests in `templates/catalog-layout.test.tsx` (acceptance, one per artboard, live parts)
- [x] tsc for `packages/ui` and `apps/web`; eslint and prettier on the touched files
- [x] `apps/web` white-label and specimen-figure suites (42) still pass
- [ ] Playwright not run locally: v1.63 wants chromium 1243, only 1248 is cached

## Rollback
Revert the commit: new files plus appended registry, export, manifest and tier-D lines.

## Progress log
- 2026-10-26: built and tested. Open gap for WB-10: blueprint 01 §9.1 names Google Workspace as
  available and BILL as coming soon, while the T5/TPL-05 canvases (and the C-14 kit) draw Google
  Drive and Gmail and BILL as available; the specimen keeps the canvases' catalogue, whose counts
  tie to §9.5 exactly (9 · 38 · 6 and every category), and WB-10 settles the seed's rows.
  The Library's installed count on the canvases is 10 against §9.5's "14 agents installed"
  (Workbench); the specimen keeps the canvases' badges (TPL-05b's Audit 3/1/1 needs them).
