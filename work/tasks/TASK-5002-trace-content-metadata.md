---
id: TASK-5002
title: "DEC-87 content and metadata projections on runs, traces, writes and items"
spec: SPEC-318
acceptance_criteria: [AC-9]
risk_zone: amber
status: done
branch: task-5002-trace-projection
worktree: agentwt
created: 2026-10-26
updated: 2026-10-26
---

## Plan keys
P-09-T08 (content and metadata projections), P-09-T01 (agent_run.read conditions) (partial).

## Plan
- **Matrix:**
  - `agent_run.read` gains `security_admin: allow` and `quality_partner: in_scope`;
  - the new `run_content.read` covers the engagement roles, plus practice_leader and quality_partner in scope, with independence required and the agent denied.
- **Agents:**
  - `runs.projection_for` asks the matrix through `allowed_actions`, so the code compares no role names;
  - the trace drops `model_text`, writes drop `target_id`, and items drop narration and `ref_id` (numbered first);
  - `projection` is added to `RunTraceOut` and `RunViewOut`.
- **Web:** the drawer shows "You can see what ran, not the client content."
- **Rollback:** revert the PR. There are no migrations.

## Progress log
- Dev smoke test:
  - the partner gets content: model text present, references present;
  - a staff member given `security_admin` temporarily in the local database (reverted afterwards) gets metadata: no model text, no references.

## Definition of done
- [x] Status vocabulary (after regenerate), classification, matrix, independence, api and route introspection tests pass.
- [x] spec318runs passes (8 tests).
- [x] check-fast passes.
