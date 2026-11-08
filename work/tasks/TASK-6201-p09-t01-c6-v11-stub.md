---
id: TASK-6201
title: P-09-T01 C6 v1.1 contract stub for dock and trace
spec: SPEC-648
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4]
risk_zone: red
status: in-review
epic: P-09
plan_key: P-09-T01
branch: s31-p09-t01
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Objective
C6 v1.1: the shapes SHL-13 and WB-09 read, additive to v1, with flags, matrix, glossary, contract
doc and E0 fixtures.

## Plan (red)
- `agents/runs_routes.py`: `RunHeaderOut`, `RunProjectionLevelOut`, `TraceSummaryOut`,
  `TraceSampleOut`, `TraceStepOut`; optional fields on `RunViewOut` (`header`, `levels`, `access`),
  `RunItemOut.session_kind`, `RunItemsOut.next_seq`, `TraceRowOut` (`phase`, `mark`,
  `duration_ms`), `RecordsReadOut` (`connection_id`, `through`), `RunWriteOut` (`state`,
  `approver_name`, `proposal_id`), `RunTraceOut` (`summary`, `access`). The `Trace` dataclass is
  untouched, so the trace-v1 export bytes do not move.
- New route `GET …/trace/steps/{step_id}`: authorise the run, 404 off, 501 on.
- `agents/runs.py`: the export manifest's `projection` is the trace's, not a constant.
- Flags `agent_dock.enabled`, `run_trace.enabled` (agents.yaml). Matrix: `eqr_reviewer` on
  `agent_run.read` and `run_content.read`; `run_trace.export` gets the read principals.
- Glossary: Run trace, Run projection, Tool card, AgentBlocks, Session item.
- `docs/contracts/agent-runs.md` §10; SPEC-648.
- Fixtures: `apps/web/src/fixtures/seed/agent-runs.ts` and `handlers/agent-runs.ts`.
- `make regenerate`, `make generate`.
- Tests (written at the end pass): `backend/tests/contracts/c06_agent_runs/test_c06_v11.py` (AC-1,
  AC-2, AC-3) and the fixture footing test (AC-4).
- Rollback: revert; no migration.

## Progress log
- `2026-11-08` — Built. Tests and gates at the S31 end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2801 | C6 v1.1 shapes, flags, the export's principals and projection | no |
