---
id: TASK-322
title: "A-06 F3/F4 slice: recorded entries in the trial balance's layers, and the SUM"
spec: SPEC-311
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: red
status: done
branch: task-322-adjustments
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan keys
A-02-T07, A-06-T09 (partial). Recorded in docs/plan/status/status-verified.csv (TASK-901).

## Plan
- **Ledger:**
  - `AdjustmentEntry`, `EntrySet` and the typed `AdjustmentSource` slot;
  - `apply_entries` and `final_totals`;
  - a layer parameter on `leadsheets`;
  - the view carries Final and the pending count.
- **Fieldwork:** `misstatements.py` (the source, plus `uncorrected_for` with bands). It registers in `api.py`. New route: `/uncorrected-misstatements`.
- **Assurance:** the line and detail outputs gain the layer fields; leadsheets take `layer`.
- **Workpapers:** `TB(..., "FINAL")`. The hash includes the recorded refs when a paper uses FINAL.
- **Web:** the layer toggle and columns in `TrialBalance.tsx`; `Uncorrected.tsx` on Findings' Entries view.
- No migration. Rollback is a revert.

## Notes
- The layer test now patches the source list, because importing fieldwork registers a source.

## Definition of done
- [x] The ledger, workpapers and fieldwork unit tests (213) pass.
- [x] A local smoke test of Final on the dev trial balance (fieldwork source registered) passes.
- [x] The spec308, spec309, spec311 and spec301 web tests (21) pass.
- [x] check-fast passes.
