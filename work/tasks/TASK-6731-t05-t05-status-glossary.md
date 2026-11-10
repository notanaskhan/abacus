---
id: TASK-6731
title: "T-05-T05: status registry (preparer memo, allocation structure, run-step context labels) and glossary rows for entity returns"
spec: SPEC-651
acceptance_criteria: [AC-0]
risk_zone: amber
status: in-review
branch: s35-t05-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: T-05-T05
---

## Objective
status.ts and the StrEnums regenerate with the new rows, and the L12 lint accepts every new code identifier.

## Plan (amber: written before the build)
- **`docs/product/status-vocabulary.yaml`:**
  - `preparer_memo`: drafting, adopted, approved, stale (all derived, T-05 §4.2).
  - `allocation_structure`: editing, pending_approval, approved, superseded.
  - `agent_run_step` context labels for TXP-00's rows (running "Running…", waiting_on_inputs "Waiting on {n} answer", failed "Stopped at {task}").
  - `tie_out_tally` already holds every T-05 word (tie · off · Check · Pending · Ties once posted · Reconciled), and `return` already carries the "Working" context label (`subbar_entity_returns`), so neither changes.
  - Regenerated: `kernel/_statuses.py`, `packages/ui/src/status.gen.ts`.
- **`docs/product/glossary.md`:** a "New terms: tax entity returns" section (workbook, workbook cell, allocation structure, allocation rung, ownership period, interest transfer, preparer memo, tie-out for entity returns, partner of a partnership). One new ban: `spreadsheet` for workbook (no identifier in code uses it; L12 checks class, function and table names).

## Progress log
- 2026-11-10: written and regenerated; the L12 lint and check-generated run at the end pass.
