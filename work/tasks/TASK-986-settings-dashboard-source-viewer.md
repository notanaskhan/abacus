---
id: TASK-986
title: T12 SettingsLayout, T11 DashboardLayout, the E5 SourceViewer shell and its independent AC tests (F-05-T45, T46, T47, T48)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: amber
status: done
epic: F-05
plan_key: F-05-T45; F-05-T46; F-05-T47; F-05-T48
branch: f05-t45-t48-settings-dashboard-viewer
created: 2026-10-23
updated: 2026-10-23
---

## Objective
- F-05-T45: "TPL-12b enables Save only when dirty, TPL-12c blocks Save with Required, TPL-12d shows
  the read-only banner, and TPL-12e toasts Firm settings saved."
- F-05-T46: "Role variants, the quiet day and Office Denver recompute from fixtures with every count
  tying to blueprint section 9.5 and KPI type at 22px or less."
- F-05-T47: "Pages render only server page images (no pdf.js, no SheetJS, no raw file), regions
  stay invisible until lit, and Download is absent from the bar."
- F-05-T48: "No client bytes reach the DOM as HTML, reveal fires its logged callback once per
  explicit click, and every viewer state is axe clean."

## Plan (amber: T47 `viewer/` is hostile content, T48 its independent tests)
- **Files.** `packages/ui/src/templates/settings-layout.tsx` (T12, `canSave`, `SettingsLock`, the
  `stepUp` slot), `templates/dashboard-layout.tsx` (T11, `DashTile`, `QueueRow`, `DeadlineRow`,
  `ActivityRow`, `QueueEmpty`), `packages/ui/src/viewer/` (`types.ts`, `source-viewer.tsx`:
  `SourceViewer`, `ReviewTree`, `FileChip`, `pageSrcAllowed`), C-13 `ValueRow` gains `help`,
  `errorAt`, `readOnly`, `lock` and the `value` kind. Specimens `t12-settings`, `tpl-12`,
  `t11-dashboard`, `tpl-11`, `c-08-source-viewer`; parity entries for T11, T12, TPL-11, TPL-12
  at Tier B (unlocked; F-05-T49 locks).
- **Contract.** C4 §3.3 and §3.4: the shell takes page sizes, region rects and mask tokens in its own
  L2 types (`ViewerPage`, `ViewerRegion`, `ViewerMask`); F-05-T44's consumer test pins the mapping.
- **Tests.** Builder: `settings-layout.test.tsx` (13), `dashboard-layout.test.tsx` (10),
  `viewer/source-viewer.test.tsx` (13). Independent (ADR-078, public exports only):
  `viewer/e5-acceptance.test.tsx` (9) and `apps/web/e2e/viewer.spec.ts` (axe over every viewer
  state idle, lit, finding and revealed; images only; no Download in a bar).
- **Migrations, flags, registry.** None. **Rollback.** Revert the commit; no screen consumes these
  yet (HOME-01, ADM-*, SHL-08 are later epics).

## Scope
**Out**
- The SHL-08 data path, the logged reveal endpoint and its audit event (P-03).
- The viewer's 420ms scroll-to-30% for matches from outside it, and drawing with the highlight
  swatch (the kit marks it as not drawing yet). Recorded in DECISIONS.md.
- TPL-11's Chicago and New York office views: the canvas's numbers for them do not foot to §9.5.

## Definition of done
- [x] packages/ui vitest green, apps/web vitest green
- [x] e2e: `viewer.spec.ts`, a11y (every specimen, forced colours, keyboard, target size), INV,
  white-label
- [x] `make check-fast` with the bundle budget

## Progress log
- 2026-10-23: built. T48's axe pass caught the evidence well: a scrolling region with nothing
  focusable in it; the well is now a focusable named region. Same lesson as F-05-T38's O6 stage:
  a scroll container with no control fails `scrollable-region-focusable`. This is the second time;
  a lint or a specimen-wide axe rule in the component tests would catch it earlier.
