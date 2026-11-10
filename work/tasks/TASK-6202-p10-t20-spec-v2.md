---
id: TASK-6202
title: P-10-T20 capability spec v2
spec: SPEC-647
acceptance_criteria: [AC-R8, AC-R1]
risk_zone: red
status: in-review
epic: P-10
plan_key: P-10-T20
branch: s31-p10-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Capability spec v2 beside v1: shapes, tools by kind, loop limits, plan policy, data classes,
untrusted inputs, and a codegen that refuses a bad spec.

## Plan (red)
- New `agents/spec_v2.py` (`AgentSpecV2`, `LimitsV2`, `ToolsByKind`, `spec_problems`,
  `registry_problems`, `AGENTS_V2` loaded and validated at import).
- New `specs/v2/` (README; no spec until P-10-T40's `runtime.conformance`), generated
  `specs/_specs_v2.py`.
- New codegen `abacus_tools/codegen/agent_specs_v2.py`, in `make regenerate`'s GENERATORS: imports
  every `agent_tools.py`, reads the matrix, refuses before rendering.
- `identity.authz.agent_denied` (exported by `identity.api`): an approved_write tool's action.
- v1 `spec.py`, `specs/*.yaml`, `_specs.py` untouched.
- Tests: `tests/unit/agents/test_p10t20_spec_v2.py` (written; run at the S31 end pass).
- Rollback: revert; nothing reads v2 yet.

## Progress log
- `2026-11-08` — Built; codegen `--check` passes on the empty folder.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2802 | Two-stage validation; denied scope actions tied to approved_write tools | no |
