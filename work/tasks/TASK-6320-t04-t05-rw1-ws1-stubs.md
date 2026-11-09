---
id: TASK-6320
title: T-04-T05 RW-1 and WS-1 contract stubs
spec: SPEC-649
acceptance_criteria: [AC-1]  # every route 501 under one action; contract docs complete
risk_zone: amber
status: done
epic: T-04
plan_key: T-04-T05
branch: s32-t04-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
RW-1 and WS-1 as classified Pydantic models and 501 routes, one action each, with contract docs.

## Progress log
- `2026-11-09` — `tax/workspace_contract.py` (18 routes), mounted in `tax.api.ROUTERS`; contract
  docs written. `make generate` (OpenAPI and the client) runs at the end pass with the other
  contract changes. The xlsx export of the allocation is not stubbed (deterministic export lands
  with its build row).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3020 | One router for RW-1 and WS-1 under `/v1/tax`; models classified TRI for values | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status done.
