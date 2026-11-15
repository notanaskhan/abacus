---
id: TASK-8046
title: "A-08-T06: confirmations contract stub (firm routes and the public /v1/confirm/* family)"
spec: SPEC-657
acceptance_criteria: [AC-0, AC-6, AC-7]
risk_zone: red
status: in-review
branch: a08-t06-confirmations-stub
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T06
---

## Objective
Contract first for confirmations: firm routes as 501 stubs under their actions, the public family
registered as link-principal routes serving POR-17 fixtures on the fixture tenant only.

## Plan (red: written before the build)
1. **Protected** `identity/routing.py`: `LINK_PRINCIPAL` marker on exactly five paths; export it.
2. **Protected** `abacus_tools/quality/banned_patterns.py`: the five paths on the exception list.
3. `assurance/confirmations_contract{,_models}.py`, `confirmations_fixtures.py`; router in
   `assurance/api.py`; error catalogue regenerated; `make generate`.
4. `docs/contracts/confirmations.md`; contract tests under `tests/contracts/a08_confirmations/`.
Rollback: revert; no table, no write.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010); plan above written before building.
- `2026-11-15` — Built (DEC-5031). ruff and pyright clean; routes mount (22); client
  regenerated. Tests written, run at the end pass.
- **Note for the end pass:** the public stub is reachable only once the ADR-152 amendment is
  accepted (Ayush); until then it serves fixtures in local and test only.
