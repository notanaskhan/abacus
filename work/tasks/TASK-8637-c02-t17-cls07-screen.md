---
id: TASK-8637
title: "C-02-T17: CLS-07 Adjustments & thresholds on T6 (fixture then live)"
spec: SPEC-700
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
branch: c02-t17-cls07
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: C-02-T17
---

## Objective
CLS-07 at /closes/$closeId/adjustments: control bar (Issues, Adjustments, Flux; threshold chip), tally strip, list pane with StatusDisc rows, class limits and total, pinned approver footer, detail cards (KV, Lines), the SHL-10 batch modal, held-entry approve with 10-second Undo, request approval, post confirm; states a, a2, b, c, c2, d, e, f, g from fixtures.

## Plan (amber)
1. backend: cas_delivery_slice.cls07_rows and fixture_export.scenario_files write scenario.cls07-entries.json (no database).
2. apps/web/src/fixtures/seed/cls07.ts: per-state PostingCloseEntriesOut and EntryOut from the export; tallies counted from rows.
3. fixtures/scenarios/CLS-07.ts serves GET …/proposed-entries:close and …/proposed-entries per state.
4. screens/CLS-07/index.tsx + copy.ts; routes/firm/closes.tsx adds /closes/$closeId/adjustments (a close is one work item).
5. screens/CLS-07/CLS-07.test.tsx: tallies 20,020 / 14,900 / 34,920 / 35,300; a, a2 modal 'Approve 4 under BH AJE thresholds v2' $20,020.00, b, c, g.
6. API client regenerated (make generate) for the C-02-T12 routes.

## Progress log
- `2026-11-18` — Built in the S50 completion round (DEC-5637). Partial: the Reasoning card (AgentText with CiteMarkers) and the Evidence card wait on the agent proposal read for a close entry (no C8 route returns a close entry's reasoning or citations yet); the Edit O2 drawer and Reject reason dialog are callbacks the route does not wire yet (CLS-06 issue on reject); the KNW-04 threshold chip and the post flow (C-02-T18 posting) are callbacks. The approver role reads the API's role label (Senior), not the handoff's 'CAS Senior'. Row sub-lines ('Aug 23–31 wages unpaid…') are not in the C8 row and are not shown. Tier C parity and axe run at the end pass. Gates and tests run once at the S50 end pass (build first, test last).
