---
id: TASK-1032
title: C-02 Workpaper kit (WorkpaperPane, SectionBand, ScheduleBar) and SourceDocGroup and SourceDocRow for the T2 canvas (F-05-T50)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T50
branch: s7-f05-t50-t53-ui-kit
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Dark section bands and schedule bars match the Workpaper kit and source-doc rows open the viewer
through a callback."

## Scope
**In**
- `packages/ui/src/workpaper/`: `SectionBand` (30 espresso, "SECTION n — TITLE", one native
  button with `aria-expanded` and no button inside, sign-off at 72% white, static variant),
  `ScheduleBar` (28), `WorkpaperSection` (band → caption → key/value rows → schedule → evidence
  table pad 14 → after-rows; collapse over 340ms, collapsed body `inert`), `WorkpaperPane`
  (chrome: 46 title, 46 tab row with the small Segmented and the Download / Open in Excel ghost
  buttons; `chrome={false}` for a host pane; the pinned Citations / Procedures footer; its own
  MatchScope and popover host). A citation lights its exact cell and row, expands a collapsed
  section first and reveals the cell 380ms later; collapsing the section or switching tabs closes
  it. `SourceDocGroup` and `SourceDocRow` in the `cockpit` (TPL-02) and `compact` (C-15) sizes;
  a row is one button that calls `onOpen(doc)`.
- `DataGrid` gains `pad` and `cellMatch` (a cell's match id from its typed locator lights the cell
  and its row through E1; INV-2).
- Specimens `c-02-section-band`, `c-02-workpaper`, `c-15-source-docs`; T2b's canvas is now the
  workpaper (`chrome={false}`, driven by the canvas's control row). `NORTHWIND_PBC` (the seed's 24
  requests in its order, with the TPL-02 file paths) checked against the seed in the app's test.

**Out**
- The TPL-02 Northwind cockpit specimen (F-05-T51). The SHL-08 viewer the callback opens is the
  screen's.

## Definition of done
- [x] 13 tests in `workpaper/workpaper-kit.test.tsx`; the app's specimen-figures test checks the
  PBC list against the seed
- [x] axe harness, INV sweep and white-label sweep over the gallery
- [x] lint, tsc, prettier for `packages/ui` and `apps/web`

## Progress log
- 2026-10-24: built. Decisions in `tokens/DECISIONS.md` (F-05-T50) and DEC-251 (the workpaper
  specimen's organisations).
