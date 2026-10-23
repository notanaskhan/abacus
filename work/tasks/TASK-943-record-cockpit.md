---
id: TASK-943
title: T2 RecordCockpit frame with the C-03 Rail kit, the C-04 Record kit, canvas host, dock slot (Agent, Viewer, Notes) and layout chip; states T2a to T2e (F-05-T40)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T40
branch: f05-t40-record-cockpit
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"T2a to T2e render with data-driven sub-lines plus discs, never colour alone, and toggling the dock
flexes the canvas between 696 and 1036."

## Scope
**In**
- `packages/ui/src/record/`: the C-03 Rail kit (`RecordRail`, `RailRow`, `PhaseRow`, `GroupBand`;
  default, outline, compact and bare; Begin… optimistic; ··· menu Open · Assign… · Mark as Done ·
  Skip phase…; ↑ ↓ across visible rows; collapsed groups `inert`) and the C-04 Record kit
  (`OverviewCard`, `AboutCard`, `RecordStatePill` with the A7 tones, `StatusDropdownPill` with the
  close transitions only, `StatRow`, `RecordBand`, `KvRowView` text, link and person picker,
  `RecordSummary`). Generic view-model types in `types.ts`; no API client.
- `packages/ui/src/templates/record-cockpit.tsx`: `RecordCockpit` (toolbar, 59 audit bar, rail
  330, canvas flex with a left title, a 42 control row, a pinned footer and its ViewState, dock 330
  with the Agent · Viewer · Notes switch, live dot, header action and composer slot) and
  `DockComposer`. The audit bar's layout chip shows and hides the dock.
- Specimens `c-03-rail`, `c-04-record`, `t2-record-cockpit` (artboards t2a to t2e) on the seed's
  names and counts; `STAFF` gains Margaret Okonkwo, Raj Malhotra and Daniel Reyes (seed-checked).
- Parity: `t2-record-cockpit.t2a` to `.t2e` at Tier B with a recorded deviation; Tier D geometry
  (rail 330, canvas 696 and 1036, dock 330, audit bar 59) in `e2e/visual/tier-d.spec.ts`.

**Out**
- Canvas content (C-02 Workpaper kit, F-05-T50), dock run rows (C-12, P-04) and the decision card
  (SHL-11, P-09): slot notes in the specimens until those land. TPL-02 Northwind specimen: F-05-T51.

## Definition of done
- [x] 13 tests in `record/record-kit.test.tsx`, 9 in `templates/record-cockpit.test.tsx`
- [x] Tier D T2 geometry (2 tests) green against the gallery
- [x] axe harness (`e2e/a11y.spec.ts`), INV sweep and white-label sweep green over the gallery
- [x] lint, tsc, prettier for `packages/ui` and `apps/web`

## Progress log
- 2026-10-23: built. vitest `src/record` 13 passed, `record-cockpit.test.tsx` 9 passed; Playwright
  visual tier D "T2 record cockpit" 2 passed; a11y "every specimen is clean" and forced colours
  passed; inv.spec and ds-white-label 6 passed. Decisions in `tokens/DECISIONS.md` (F-05-T40).
