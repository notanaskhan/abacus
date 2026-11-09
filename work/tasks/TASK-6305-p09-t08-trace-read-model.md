---
id: TASK-6305
title: P-09-T08 trace read model, v2 timeline, step detail, records read, writes
spec: SPEC-648
acceptance_criteria: [AC-1]
risk_zone: red
status: in-progress
epic: P-09
plan_key: P-09-T08
branch: s32-p09-t08
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
WB-09's read model over v2 runs: summary, timeline, step detail with samples, records read by
source, writes with approvers; content and metadata; region from the register; TINs scrubbed.

## Plan
- New `agents/trace.py` (timeline, sources, samples slot, region, args summary).
- `agents/runs.py`: `Trace.summary/v2_rows/sources`, `records_read_for` v2, `step_detail`, write
  states, `LEGACY_PHASE`, export bytes unchanged.
- `agents/runs_routes.py`: rows, summary, step route live (no 501), `TraceRowOut.kind` widened.
- Migration 0751 `run_step_trace_refs` (expand-only) + registry UPDATE_COLUMNS.
- Contract §12; DEC-3005.
- Tests: `tests/unit/agents/test_p09t08_trace_v2.py`,
  `tests/integration/agent_tests/test_p09t08_trace_read_model.py`.
- Rollback: revert; 0751 downgrade drops both columns.

## Progress log
- `2026-11-09` — Built; ruff, pyright clean; tests written, not run (S32 end pass). Partial: no
  module registers a sample resolver yet (each module's tools land from P-10-T28), so samples
  stay empty; `through` names "Accrued" but not a connection's name (agents does not depend on
  integrations; the client resolves the id). API client regenerates at the end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3005 | Phase and mark maps, metadata titles, step detail 404s, write states, 0751 | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status partial.
- `2026-11-09` — Partials round (branch s32p-p09-t10, DEC-3024): WB-09 a2 shows the first five
  returns read (TAX-02 seed, linking to each return) in fixtures. The connection name in "Records
  read" stays open: no firm-side connection lookup by id; needs a C6 `connection_label` resolved
  by the connections module (W-01).
