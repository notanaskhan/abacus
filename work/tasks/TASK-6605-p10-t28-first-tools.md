---
id: TASK-6605
title: "P-10-T28: First tools in their owning modules with tool.<name>@v1 description prompts"
spec: SPEC-647
acceptance_criteria: [AC-R1, AC-R6]
risk_zone: red
status: in-review
branch: s34-p10-t28
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T28
---

## Objective
Each tool has a registered description prompt, returns at most 200 rows with IDs and
code-computed totals, and refuses walled or out-of-scope records in a test.

## Plan (red)
1. `kernel/agent_tools.py` (new, PROTECTED): `ToolDecl` and `ToolCaller`, the ADR-106 slot. The
   owning modules cannot import `agents` (it imports them) and `ledger` imports nothing, so they
   declare tools as records and `agents` registers them (DEC-3204).
2. `<module>/agent_tools.py` (new) in engagements (list, read, read_graph, read_team, and
   `methodology.read_step` over methodology's `step_of_version`), requests (list_items,
   read_item), evidence (search, read_extraction, list_uploads), ledger (read_tb,
   compare_periods, tie_out), agents (knowledge.search, activity.read); each api exports
   `AGENT_TOOLS`.
3. `agents/tools/catalogue.py` (new): registers every declaration through `register_tool`.
4. Prompts `ai_gateway/prompts/tool.<name>/v1.txt` (15).
5. Matrix: `agent: task_scope` on `engagement.read`, `activity.read`, `knowledge.read` and
   `trial_balance.read` (regenerated `_matrix.py`); a spec reaches them only by listing the tool.
6. Tests: `tests/unit/agents/test_p10t28_first_tools.py`; runtime refusals in P-10-T31.
Rollback: revert; no spec lists these tools yet, so nothing runs them.

## Progress log
- `2026-11-10` — Built; ruff, pyright clean; the app imports and 15 tools register. Tests not run
  (end pass). Partial: no pagination (`ToolPageIn` lives in `agents`, which the owning modules
  cannot import); each list answers its first 200 rows with the full total and `truncated`
  where it applies. `knowledge.search` is text match, not the embedding search (C17 v1 has no
  gateway port in a tool). The C17 v1 snapshot is re-read at the end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3204 | The kernel declaration slot; the four matrix rows; read_step in engagements | no |
