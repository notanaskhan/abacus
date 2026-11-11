---
id: TASK-6806
title: "T-04-T28: Backend scenario slices (scenarios/brightwater_hale) through service APIs: Feld TY2025 return worksheets and field versions, issues, checkpoints; make fixtures parity test"
spec: SPEC-649
acceptance_criteria: [AC-10]
risk_zone: amber
status: in-review
branch: s36-t04-t28
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-04-T28
---

## Objective
make seed-demo and fixture mode show identical counts and figures for every in-scope artboard, and
the scenario loads on staging under the demo clock.

## Plan (amber: written before the build)
1. `tax/workspace_seed.py`: `record_synthetic_workspace` (synthetic firms only): worksheets,
   sections and fields through the unit of work as the named person, each value a field version
   (`agent_suggested`, cause `import`) and the cached current value through `write_field`, one
   `return_worksheet.seeded` audit event per worksheet; idempotent per `(return, key)`.
2. `tax_workspace_slice.py`: Feld's "Sch E p2 — Ridgeline" (307,900 = 141,634 + 96,989 + 69,277;
   box 5 4,600; distributions 150,000; 18A line empty) and "New York IT-201" (line 20 at 0; NY and
   NYC tax engine lines); TAX-06's six non-system issues (3 open, 3 resolved Aug 27–28); TAX-07's
   "Initial draft", "K-1 box 18A", "Manager review" checkpoints. Loader handlers and needs.
3. Parity test against `apps/web/src/fixtures/seed/tax-workspace.ts`.
4. Rollback: revert; the slice is opt-in.

## Progress log
- `2026-11-11` — Built (S36). Parity test written, not run (end pass).

## Partials
- Not yet in the slice: the 41 documents' approval timeline (TAX-04/05 counts), the Ridgeline and
  Shah K-1 activities (TXI-02), the residency facts (TXI-03) and J19's Okafor and Thornbury
  activity rows; `make fixtures export` parity for those artboards waits on them.
- Issues are raised as Kevin Osei (the handoff says "Created by Accrued Agent", which needs the
  drafter's run).
- The over-HTTP export/import suite on these worksheets (T-04-T30's) runs at the end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3406 | Synthetic workspace recorder, slice scope, deviations | no |
