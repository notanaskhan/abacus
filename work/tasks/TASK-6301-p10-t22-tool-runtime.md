---
id: TASK-6301
title: P-10-T22 tool registry runtime and the C17 v1 freeze
spec: SPEC-647  # AC-R2 to AC-R7, AC-G4
acceptance_criteria: [AC-R2, AC-R3, AC-R4, AC-R5, AC-R6, AC-R7]
risk_zone: red
status: done
epic: P-10
plan_key: P-10-T22
branch: s32-p10-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
`call_tool(agent, call)`: per-call authorisation, scope pinning, §7216 before any query, grants,
idempotency, row limits, TIN scrub, access events and `<untrusted>` rendering; C17 v1 frozen.

## Plan
- `agents/tools/runtime.py` (new, protected): `ToolCallIn`, `ToolOutcome`, `ToolTargets`,
  `call_tool`, `for_model`, `pinned_scope`, `consumer_ref`. Order in the module docstring and the
  contract's §6 table.
- `agents/tools/registry.py`: `ToolPageIn`, `ToolPageOut`, `row_fields`; `validate_tool` holds the
  shapes (rows carry ids, pages, untrusted names output fields, writes answer identifiers only).
- Migration 0750 `agent_tool_calls` (claimed -> done once, trigger; RLS; column grants); agents
  registry rows (TABLES, INSERT_COLUMNS, UPDATE_COLUMNS).
- `agents/api.py` exports; access kind `agent_tool.restricted_read`.
- `abacus_tools/contracts.py`: `IN_PROCESS` contracts; `tests/contracts/c17_tools/v1.json`.
- Docs: `docs/contracts/tool-registry.md` §5 to §9, register row frozen.
- Tests: `tests/contracts/c17_tools/test_c17_runtime.py` (AC-R2 to R7, G4, freeze),
  `tests/integration/test_p10t22_agent_tool_calls.py` (0750).
- Rollback: revert; 0750 downgrade drops the table. No flag: nothing registers a tool until
  P-10-T28, and the harness that calls `call_tool` is P-10-T25.

## Progress log
- `2026-11-09` — Built. Static checks on touched files (ruff, pyright) clean. Tests written, not
  run (S32 end pass). `records_read` is answered on the outcome; the harness writes it to the step
  with the step's state, so a read writes no audit event.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3001 | Runtime order, error codes, idempotency ledger 0750, C17 v1 in-process freeze | no (ADR-233 covers it) |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status done.
