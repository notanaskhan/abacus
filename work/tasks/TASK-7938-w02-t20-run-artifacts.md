---
id: TASK-7938
title: "W-02-T20: run artifacts and drill (preview, audited download, code-rendered drill)"
plan_key: W-02-T20
spec: SPEC-653  # W-02 §3.8, §4.3
acceptance_criteria: [AC-R2, AC-R3, AC-R4]
risk_zone: red
status: in-review
branch: w02-t20-run-artifacts
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
The preview matches the stored workbook, a download writes one audit event, and the Action
required 11 drill lists 11 returns with no model call.

## Plan (red)
- `agents/run_artifacts.py` (new): who may read (engagement run: the action on its engagement;
  firm-level: the person it ran for), preview from stored bytes, audited download, drill with
  the `register_drill_source` slot; `agents/run_artifacts_contract.py` goes live.
- `evidence/run_files.py`: `read_run_artifact` (exported). `tax/board.py`: `season_group`,
  registered as `status` in `tax/api.py`. Audit fallback: `run_artifact.downloaded`,
  `session.drill_appended`. Client regenerated (the 501s are gone).
- Tests: `backend/tests/unit/agents/test_w02t20_run_artifacts.py`.
- Rollback: revert the PR (routes return to 501; drill items written stay insert-only).

## Partial
- The drill item is not announced on the session's realtime topic (agents cannot import
  workbench's event); the route returns the item and WB-03 inserts it.

## Progress log
- 2026-11-14: built; tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4933 | stored-bytes preview, one audit per download, drill source slot, firm-run reader | no |
