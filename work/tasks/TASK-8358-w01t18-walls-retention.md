---
id: TASK-8358
title: "W-01-T18: The row's rest: client-company walls and integration_event retention registration"
spec: SPEC-659
acceptance_criteria: [AC-17, AC-18, AC-19]
risk_zone: red
status: in-review
branch: w01t18-walls-retention
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T18
---

## Objective
Spec section: SPEC-659 AC-17 to AC-19, P-14. The row's rest: client-company walls and integration_event retention registration.

## Plan (red)
1. `tests/unit/integrations/test_w01t18_walls_retention.py`: a walled client is neither named nor counted in WB-11 d's list and a search cannot find it; `integration_event` is a retention record class.
2. Fix the finding: `integration_event` added to `RECORD_TYPES` (years are content, ADR-179 proposed).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. 3 passed; ruff and pyright clean. Finding fixed: the record class was not registered. Fake-adapter refusal (W-01-T09) and membership-end revocation (W-01-T08 AC-13) were already covered. Gates and
  tests run once at the S47 end pass (build first, test last).
