---
id: TASK-7628
title: T-05-T38 TXP-11 Workpaper — Ridgeline workbook screen
plan_key: T-05-T38
spec: SPEC-651
acceptance_criteria: [AC-F4]  # after the fix H8:H12 124…1,550, J13 = J15 = 6,866,200, the amber dot clears
risk_zone: green
status: in-review
branch: t05-t38-txp11-screen
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
TXP-11 on the entity return's Workpaper tab, on WorkbookGrid, with the in-cell edit and its 409.

## Plan
- `apps/web/src/screens/TXP-11/{copy.ts,index.tsx,Workpaper.tsx,TXP11.test.tsx}`;
  `screens/TXP-00/EntityReturn.tsx` dispatches the Workpaper tab.
- Fixtures: `seed/tax-entity-sheets.ts` (05 Capital before, proposed, after; 01 Trial Balance
  rows 6–18), handler `GET …/workbook/sheets/{sheet}`, scenario b marked proposed.
- Manifest TXP-11 `fixture` at `/tax-returns/$returnId/workpaper`; screen contract notes.

## Partial
- a2, a3, d (SHL-07, SHL-09, SHL-08 overlays) not wired here; version picker read-only label;
  Open in Excel a callback (T-05-T60); server sheet titles differ from the handoff's.

## Progress log
- `2026-11-12` — Screen and fixtures built (DEC-4623). Tests at the end pass.
