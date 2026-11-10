---
id: TASK-6210
title: P-09-T03 AgentBlocks v1, the JSON Schema export
spec: SPEC-648
acceptance_criteria: [AC-6]
risk_zone: red
status: in-review
epic: P-09
plan_key: P-09-T03
branch: s31-p09-t03
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Finish TASK-5004: the server schema, validators, fact registry, sanitise, number provenance and
copy lint were built; the row's remaining clause is the JSON Schema export to packages/api-client.

## Plan (red)
- `abacus_tools/codegen/agent_blocks_schema.py` (in `make regenerate`, `--check` in
  `check-generated`): `packages/api-client/schemas/agent-blocks.v1.json`, exported as
  `@abacus/api-client/schemas/agent-blocks.v1.json`.
- Verified against ADR-230 (accepted; P-24): v1's nine parts, closed, numbers by fact. ADR-230's
  v2 `h` and `ul` parts are F-06-T15's, not this row's.
- Tests: `tests/unit/agents/test_p09t03_blocks_schema.py`.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2810 | The schema is generated from the model; the server stays the authority | no |
