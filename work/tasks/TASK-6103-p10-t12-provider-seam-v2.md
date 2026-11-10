---
id: TASK-6103
title: "P-10-T12 provider seam v2: ConverseRequest/ConverseResponse, converse() on direct and Bedrock, FakeModel trajectories"
spec: SPEC-000  # row (P-10-T12)
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-10
plan_key: P-10-T12
branch: s30-p10-t12
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
ADR-234 §7 and chapter 05 §5.3.2: a conversation seam beside `complete()`: messages with text, tool_use, tool_result and document blocks, tools with cached definitions, tool_choice, cached system layers, stop_reason and cache tokens; `converse()` on both real routes; FakeModel trajectory scripts. `ModelRequest`, `ModelResponse` and `complete()` stay as they are.

## Plan
- `ai_gateway/providers.py` (protected): block types, `ConverseMessage`, `SystemBlock`, `ToolSpec`, `ConverseRequest`, `ConverseResponse`, `ConversingProvider` (runtime-checkable), `conversing()`, `ToolCallTurn`/`FinalTurn`/`Trajectory`, `FakeModel.script()/scripts()/converse()`.
- `routes/_anthropic.py`: `converse_args` (system layers with cache breakpoints, tools with a breakpoint after the last, tool_choice, document blocks as base64) and `to_converse_response` (stop reason map, cache reads and writes apart); `message_args`/`to_response` untouched.
- `routes/direct.py`, `routes/bedrock.py`: `converse()` with the same error mapping; `routes/__init__.py`: `route_converser()`.
- Tests: `tests/unit/ai_gateway/test_p10t12_provider_seam.py`.
- Rollback: revert; nothing calls `converse()` yet (P-10-T19's `converse.py` is the first caller).

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean on ai_gateway and the test.

## Decisions made during this task
DEC-2701
