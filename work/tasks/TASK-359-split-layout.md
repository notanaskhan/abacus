---
id: TASK-359
title: SplitLayout with 12 presets, ResizeGutter and the 1280 drawer collapse (F-05-T29)
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T29
branch: f05-t29-split
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Preset widths match chapter 04 section 3.11, gutters clamp between 280px and 60 percent, and the
third column becomes a drawer at 1280px or less."

## Scope
**In**
- `packages/ui/src/layout/split-presets.ts`: the 12 presets as data, `dragTarget`, `roomFor`,
  `clampWidth`, `splitStorageKey`.
- `packages/ui/src/layout/split-layout.tsx`: `SplitLayout` (floating panes, row that never
  scrolls, persisted widths behind try/catch, the ≤1280 drawer through the E3 `Drawer`),
  `ResizeGutter` (separator; drag, ←/→ 16px, Enter or double click resets), `NestedSplit`
  (`hair`, `well`), `useNarrowLayout`.
- C-09 specimens.

**Out**
- Adopting SplitLayout in screens: each screen with its own task. The tabsbar ViewToggle that
  opens the drawer is the screen's (SplitLayout takes `drawerOpen`).

## Definition of done
- [x] 16 tests in `layout/split-layout.test.tsx`
- [x] The F-05-T24 harness over the new specimens (axe found a gutter without `aria-valuenow`; fixed)
- [x] `make check-fast`

## Progress log
- 2026-10-22: built and merged.
