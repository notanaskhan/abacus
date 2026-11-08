---
id: TASK-6203
title: P-10-T19 ai_gateway/converse.py
spec: SPEC-647
acceptance_criteria: [AC-G1, AC-G2, AC-G3, AC-G4, AC-G5, AC-G7]
risk_zone: red
status: in-review
epic: P-10
plan_key: P-10-T19
branch: s31-p10-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Objective
`converse()`: one gateway conversation turn with tool use under every `call()` invariant.

## Plan (red)
- New `backend/src/abacus/ai_gateway/converse.py`: `ConverseCall`, `ConverseTool`,
  `ToolCallRequest`, `ConverseResult`, `converse()`. Reuses the gateway's own admission
  (`_admitted`, `_candidate_routes`, `_next_route_exists`), failover (`_route_failed`), run spend
  (`_spent_by_run`), boundary, §7216 and budget checks. `call()` untouched.
- One usage row (with `step_id`, `session_id`, 0681) and one `model.called` per attempt; access
  events once per call; inputs by hash only.
- Tool arguments validated against each tool's input model; unknown tool or invalid argument:
  one repair (code and path), then `escalated`. A refusal stop reason is never repaired.
- Tests: `tests/integration/agent_tests/test_p10t19_converse.py` (run at the end pass).
- Rollback: delete the file; nothing calls it yet (P-10-T21's harness will).

## Progress log
- `2026-11-08` — Built; pyright and ruff clean on the file.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2803 | converse() reuses call()'s admission; cache tokens priced as input | no |
