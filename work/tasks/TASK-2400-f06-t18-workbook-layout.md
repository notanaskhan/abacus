---
id: TASK-2400
title: F-06-T18 T6 WorkbookLayout, T6a/b/c
spec: SPEC-400
acceptance_criteria: [AC-26, AC-27, AC-28, AC-29, AC-32]
risk_zone: green
status: in-review
epic: F-06
plan_key: F-06-T18
branch: s19-f06-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
The T6 WorkbookLayout template: a 50 tabsbar with two small SegmentedGroups at x12 in one row, the
44 control bar (view Segmented, centred title, ghost Open in Excel and Download callbacks), the 52
tally strip, statement panes on the F-05 grammar, the 452 PaneScroller and the Building state;
states T6a (ties), T6b (off) and T6c (building).

Acceptance: "Both tab groups fit one 50 px row at 1400, T6b links off 6,200 to Issue 2 through a
callback, and T6c shows Pending pills and skeleton rows with no sign-off control."

## Scope
**In**: `packages/ui/src/templates/workbook/` (types, WorkbookLayout with ControlBar and
PaneScroller, index, tests); the T6 gallery board a/b/c (`apps/web/src/gallery/specimens/T6/`);
parity entries; the T6 steps of `e2e/specimens/f06-workbook.spec.ts`.
**Out**: calc tree and source grid, T6e (F-06-T19); SignOffSlots, T6d and TPL-06a–e (F-06-T20);
the independent suite (F-06-T21); the T22 lock.

## Context to load
- `docs/plan/epics/F-06.md` §3 F5 (Stories 5.1–5.4, 5.7), §5.2; `docs/screens/T6.md`
- Handoff `T6 Workbook schedule grid/` (spec, T6a–c) and canvas `Wave 0 - Foundations.dc.html#t6`
  (`t6data`, `t6tally`, `t6vals`)
- `packages/ui/src/data/{tally-strip,variance,data-grid}.tsx`, `templates/document-on-well/`

## Plan
Files: `packages/ui/src/templates/workbook/{types.ts,WorkbookLayout.tsx,index.ts,WorkbookLayout.test.tsx}`;
`packages/ui/src/templates/index.ts`; `apps/web/src/gallery/specimens/T6/{index.tsx,copy.ts}` and
`gallery/specimens/index.ts`; `docs/design/parity-manifest.json`;
`apps/web/e2e/specimens/f06-workbook.spec.ts`; DECISIONS.md, decision log (DEC-1450),
`docs/screens/T6.md`.
Migrations, registry, flags: none. Protected files: none.
Tests: kit Vitest (tabsbar one row, control bar callbacks, tally slot, off → onOpenIssue, variance
exception → onOpenIssue, statement formatting, no sums in source, Building pills/skeletons/disabled
Sign off…, HumanAction refuses an agent, scroller arrow keys, no T18 behaviours); the walk with axe
and the Tier D geometry step.
Rollback: revert the PR; nothing consumes the kit yet.

1. [x] Types. 2. [x] Layout, ControlBar, PaneScroller. 3. [x] T6 board a/b/c.
4. [x] Tests, walk, parity entries, docs. 5. [ ] End review run.

Tests (mapped to ACs): AC-26 → "tab groups", "control bar", "tally strip", "sized panes",
`test_ac26_*`; AC-27 → "off 6,200 links…", "variance exception…", `test_ac27_*`; AC-28 →
"statement figures…", "no code path…adds numbers"; AC-29 → "Building…", `test_ac29_*`; AC-32 →
the export callbacks in "control bar".

## Progress log
- `2026-10-30` — Built on `s19-f06-t18` (build-only; tests run at the S19 end review).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1450 | chrome in the shell's tabs slot, kit-enforced Pending while building, issue refs, board data, Calculation disabled until T19 | no |

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review; F-06-T19 adds the calc tree (e), F-06-T20 the sign-off slots (d) and TPL-06.
