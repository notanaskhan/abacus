---
id: TASK-6204
title: P-09-T04 converse runs the output-check registry
spec: SPEC-648
acceptance_criteria: [AC-7]
risk_zone: red
status: in-review
epic: P-09
plan_key: P-09-T04
branch: s31-p09-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Finish TASK-5005: the registry existed with its settle rule; `converse()` (P-10-T19) now runs it.

## Plan (red)
- `ConverseCall.output_kind`; after a structured final turn validates, `settle(kind, output,
  repairs_used)`: passed shows it; repair asks once with the check's code and path; unsupported
  answers status `unsupported` with no output. An unregistered kind is unsupported at once.
- `call()` untouched; test pins that its source never consults the registry.
- Tests: `tests/integration/agent_tests/test_p09t04_converse_output_checks.py`.
- Rollback: drop the field; the registry stays inert.

## Progress log
- `2026-11-08` — Built on P-10-T19.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2804 | `unsupported` is its own converse status | no |
