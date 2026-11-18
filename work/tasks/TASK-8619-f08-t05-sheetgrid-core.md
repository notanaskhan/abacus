---
id: TASK-8619
title: "F-08-T05: SheetGrid core: typed columns, glyph headers, frozen select and Key, virtualised rows, bands, filter row, status bar"
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: f08-t05-sheetgrid-core
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: F-08-T05
---

## Objective
Spec section: docs/plan/epics/F-08.md A1, §5. SheetGrid core in packages/ui/src/sheet with the 11 column types, Lucide glyph headers and an intents-only column menu, frozen 28 px select and 96 px Geist Mono Key, virtualised rows (E4 row-window), SectionBand 31 / sub-band 28 with the server total, filter row, 30 px status bar.

## Plan (green)
1. packages/ui/src/sheet/{types.ts,glyphs.ts,SheetGrid.tsx,index.ts}; types named SheetGrid* (overlays already exports SheetColumn/SheetRow).
2. Exported from packages/ui/src/index.ts (tree-shaken: no production chunk imports it; no package.json change, F-08 G3).
3. SheetGrid.test.tsx: 1,000 rows virtualise with aria-rowcount and aria-rowindex; select and Key sticky at 28 px; glyph per header; no $ or zebra classes; dark band with the server total; agent intents only on the agent column; suggested values ink-2; locked-row Lock glyph.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5619). Not run: vitest at the end pass. Editing and locks are F-08-T06, agent-cell states F-08-T07 (S51). Gates and tests run once at the S50 end pass (build first, test last).
