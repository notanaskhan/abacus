---
id: TASK-6302
title: P-10-T21 context builder v2 (context_v2.py)
spec: SPEC-647  # ADR-234 §5; chapter 05 "Context builder v2"
acceptance_criteria: [AC-G6]  # call() untouched; the builder's own criteria (byte-identical prefixes, tool results wrapped, registry instructions only) are ADR-234 §5, tested as AC-1..AC-3 in the unit file
risk_zone: red
status: done
epic: P-10
plan_key: P-10-T21
branch: s32-p10-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
`ai_gateway/context_v2.py`: nine fixed layers for prompt caching, per-tier budgets, data subjects,
wrapped tool results, compaction hook.

## Plan
- New `ai_gateway/context_v2.py` (protected): `ContextV2Builder`, `ContextV2` (`prefix()`,
  `prefix_sha256`, `tokens()`), `OfferedTool`, `render_tool_result`, `tool_result_block`,
  `register_compactor`, `InstructionsNotRegistered`, `UnwrappedToolResult`.
- Re-exported from `abacus.ai_gateway`; `agents.tools.runtime.for_model` renders through
  `render_tool_result`, so one wrapping serves both.
- `call()` and v1 `ContextBuilder` untouched (AC-G6).
- Tests: `tests/unit/ai_gateway/test_p10t21_context_v2.py`.
- Rollback: revert; nothing calls the builder until the harness (P-10-T25).

## Progress log
- `2026-11-09` — Built. ruff and pyright clean on touched files. Tests written, not run (S32 end
  pass). Stacked on P-10-T22 (runtime's `for_model` now delegates here).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3002 | Tools as sorted provider tool definitions (not a duplicated system block); budgets and shares; compaction without a compactor drops turns and records it | no (ADR-234 §5) |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status done.
