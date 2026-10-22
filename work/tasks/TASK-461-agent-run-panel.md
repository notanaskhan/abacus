---
id: TASK-461
title: "P-09 first slice: the agent run panel and run trace over existing runs"
spec: SPEC-318
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6]
risk_zone: amber
status: done
branch: task-461-agent-runs
worktree: agentwt
created: 2026-10-22
updated: 2026-10-22
---

## Plan keys
Q-02-T45, P-09-T07, P-09-T08, P-09-T10, P-09-T11 (partial). Recorded in docs/plan/status/status-verified.csv (TASK-901).

## Plan
- **ai_gateway:** `attempts.py`, with `attempts_for(tenant, run_id)` over `usage_records`.
- **Evidence:** `decisions_on_screenings`, plus the `decisions_for_screenings` repository read (LIST_EXEMPT).
- **Agents:**
  - `runs.py`: list, trace and canonical export;
  - `runs_routes.py`: the `engagement_runs_router` and `runs_router`;
  - in the repository, `engagement_runs` (`visible`) and `screening_results_of_run` (LIST_EXEMPT).
- **Matrix:** `agent_run.read` and `run_trace.export` (agent deny), both independence-bound.
- **Web:** `legacy/AgentRuns.tsx` (the panel and TraceDrawer), on the Activity route above the feed.
- **Rollback:** revert the PR. There are no migrations.

## Progress log
- Dev smoke test, as the dev engagement's partner:
  - 2 screener runs listed;
  - the trace has 4 rows (start by Dana Leader, one model call, "Proposed ready for review" with 2 citations, finish);
  - the canonical bytes are stable across reads.

- Rebased onto main at 44aea4e. Fixed pins that main had left stale: MARKED gained the five C3 stub actions (TASK-413), and the email-template import went into NOT_CREATING (TASK-401, idempotent, 200). Regenerated `error-codes.yaml`.
- Main still has the other stream's breakage, which I didn't touch:
  - validate_docs (TASK-391–398);
  - a pyright error in `tests/unit/tools/test_review_status_registry.py`;
  - web tsc errors (ReviewNoteOut, CapabilitiesOut.nav, status.ts).

## Definition of done
- [x] tests/unit/agents/test_runs.py (9), plus the independence, app-gates and matrix pins, pass.
- [x] spec318runs (4) and spec027agent pass.
- [x] check-fast passes for this change's files; the other stream's failures on main are listed above.
