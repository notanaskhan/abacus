---
id: TASK-8202
title: "G-04-T03: contract stubs for the platform console, plan & usage and support"
spec: SPEC-680
acceptance_criteria: [AC-2, AC-15]
risk_zone: red
status: in-review
branch: g04-t03-contract-stubs
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-15
updated: 2026-11-15
plan_key: G-04-T03
---

## Objective
Classified Pydantic models and 501 routes for the three screen families, typed fixtures, three
contract docs, the regenerated client.

## Plan (red)
1. `platform/plan_usage_contract.py`, `support_contract.py` (firm, flag-gated), `console_contract.py`
   (staff section actions).
2. **Protected** `identity/routing.py`: `staff_action()` mounts staff-section actions on
   `current_staff`.
3. `platform/api.py` ROUTERS; `platform/g04_fixtures.py`; error-code catalogue; `make generate`.
4. Contract docs; `tests/unit/test_g04_contract_stubs.py`.
Rollback: revert; no live route changes.

## Progress log
- `2026-11-15` — Built (DEC-5203). Imports clean, client regenerated. **Partial:** frontend
  fixture scenarios per artboard ride G-04-T13. Mistake made twice: `errors=(422, …)` (422 is
  default; only 409/410/413/415/416/423/429/501/503 may be declared) — candidate lint message.
- `2026-11-15` — `tests/unit/test_g04_contract_stubs.py` 74 passed. Lesson: running one file under
  `tests/unit/platform/` alone shadows the stdlib `platform` (hypothesis fails at import); new
  unit tests for this lane sit at `tests/unit/` root.
